"""Open a DOQS machine repo in Eclipse SysON and export .sysml files back.

Canonical models stay in architecture/*.sysml. SysON is a local Docker web
app; this script creates a project named after the machine, imports those
files, and writes them back after graphical edits.

    python doqs/scripts/syson.py ui       # control panel in the browser (or double-click syson.bat)
    python doqs/scripts/syson.py open     # start SysON, import if needed, open browser
    python doqs/scripts/syson.py save     # export SysON documents over architecture/*.sysml
    python doqs/scripts/syson.py reload   # delete the project and re-import from git (drops diagrams)
    python doqs/scripts/syson.py stop     # stop containers; Postgres volume (diagrams) is kept
    python doqs/scripts/syson.py status   # Docker + project summary

Run from the machine repository root (parent of doqs/). First-time setup:
install Docker Desktop, then see docs/syson.md.

Stdlib only — no pip packages.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import subprocess
import sys
import time
import tomllib
import uuid
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from check_links import IMPORT_RE
from naming_rules import is_under_doqs_submodule, repo_root_from_script

DOQS_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = DOQS_ROOT / "tools" / "syson" / "docker-compose.yml"
COMPOSE_PROJECT = "doqs-syson"
DEFAULT_URL = "http://localhost:8080"
DOCKER_DESKTOP_URL = "https://docs.docker.com/desktop/setup/install/windows-install/"
WAIT_SECONDS = 300
DEFAULT_SKIP_DOCUMENTS = frozenset({"SysMLv2.sysml"})
UI_COMMANDS = frozenset({"open", "save", "reload", "stop", "status"})
PANEL_HOST = "127.0.0.1"
PANEL_PORT = 8765
PANEL_HTML = DOQS_ROOT / "tools" / "syson" / "control-panel.html"

GRAPHQL_ENDPOINT = "/api/graphql"
GRAPHQL_UPLOAD_ENDPOINT = "/api/graphql/upload"
PROJECT_DOWNLOAD_ENDPOINT = "/api/projects/{project_id}"
DOCUMENT_DOWNLOAD_ENDPOINT = (
    "/api/editingcontexts/{editing_context_id}/documents/{document_id}"
)

FETCH_EDITING_CONTEXT_QUERY = """
query FetchEditingContext($projectId: ID!) {
  viewer {
    project(projectId: $projectId) {
      currentEditingContext {
        id
      }
    }
  }
}
"""

UPLOAD_DOCUMENT_MUTATION = """
mutation UploadDocument($input: UploadDocumentInput!) {
  uploadDocument(input: $input) {
    __typename
    ... on UploadDocumentSuccessPayload {
      id
      report
    }
    ... on ErrorPayload {
      messages {
        body
        level
      }
    }
  }
}
"""

DELETE_PROJECT_MUTATION = """
mutation DeleteProject($input: DeleteProjectInput!) {
  deleteProject(input: $input) {
    __typename
    ... on ErrorPayload {
      messages {
        body
        level
      }
    }
  }
}
"""


class SysonError(Exception):
    """User-facing failure; CLI prints the message and exits 1."""


# --- Machine repo helpers (pure; unit-tested) ---------------------------------


def _is_tools_repo(path: Path) -> bool:
    return (path / "scripts" / "license_rules.py").is_file() and (
        path / "templates" / "licensing"
    ).is_dir()


def looks_like_machine_repo(path: Path) -> bool:
    return (path / "okh.toml").is_file() or (path / "architecture").is_dir()


def default_machine_root() -> Path:
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if _is_tools_repo(candidate):
            continue
        if looks_like_machine_repo(candidate):
            return candidate
    submodule_parent = repo_root_from_script()
    if looks_like_machine_repo(submodule_parent) and not _is_tools_repo(
        submodule_parent
    ):
        return submodule_parent
    raise SysonError(
        "Could not find a machine repository (okh.toml or architecture/).\n"
        "Run from the machine repo root (parent of doqs/) or pass --root PATH."
    )


def project_name(root: Path) -> str:
    okh = root / "okh.toml"
    if okh.is_file():
        with open(okh, "rb") as f:
            data = tomllib.load(f)
        name = str(data.get("name") or "").strip()
        if len(name) >= 3:
            return name
    name = root.name.strip() or "machine"
    if len(name) < 3:
        name = f"{name}-machine"
    return name


def collect_sysml(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.sysml"):
        if is_under_doqs_submodule(path, root):
            continue
        rel_parts = path.relative_to(root).parts
        if any(part.startswith(".") or part == "__pycache__" for part in rel_parts):
            continue
        if "architecture" not in rel_parts:
            continue
        files.append(path)
    return sorted(files, key=lambda p: str(p).lower())


def _imported_targets(sysml: Path) -> list[Path]:
    text = sysml.read_text(encoding="utf-8")
    targets: list[Path] = []
    for match in IMPORT_RE.finditer(text):
        targets.append((sysml.parent / match.group(1)).resolve())
    return targets


def import_order(files: list[Path]) -> list[Path]:
    """Topological order: a file is imported only after the files it imports."""
    by_resolved = {path.resolve(): path for path in files}
    deps: dict[Path, list[Path]] = {path: [] for path in files}
    for path in files:
        for target in _imported_targets(path):
            if target in by_resolved:
                deps[path].append(by_resolved[target])

    remaining = set(files)
    ordered: list[Path] = []
    while remaining:
        ready = [
            path
            for path in remaining
            if all(dep not in remaining for dep in deps[path])
        ]
        if not ready:
            ordered.extend(sorted(remaining, key=lambda p: str(p).lower()))
            break
        ready.sort(key=lambda p: str(p).lower())
        pick = ready[0]
        ordered.append(pick)
        remaining.remove(pick)
    return ordered


def document_name(rel_path: Path, all_rels: list[Path]) -> str:
    """SysON document name: basename when unique, else joined relative parts."""
    names = [path.name for path in all_rels]
    if names.count(rel_path.name) == 1:
        return rel_path.name
    return "__".join(rel_path.parts)


def path_for_document(name: str, root: Path, files: list[Path]) -> Path | None:
    rels = [path.relative_to(root) for path in files]
    for rel, path in zip(rels, files, strict=True):
        if document_name(rel, rels) == name:
            return path
    matches = [path for path in files if path.name == name]
    if len(matches) == 1:
        return matches[0]
    return None


def extra_export_path(root: Path, document_name_value: str) -> Path | None:
    """Where to write a SysON-only document that is not in the repo yet."""
    if not document_name_value.lower().endswith(".sysml"):
        return None
    if "/" in document_name_value or "\\" in document_name_value:
        return None
    if "__" in document_name_value:
        parts = document_name_value.split("__")
        return root.joinpath(*parts)
    return root / "architecture" / document_name_value


def looks_like_textual_sysml(content: bytes) -> bool:
    stripped = content.lstrip()
    if not stripped:
        return False
    if stripped.startswith(b"{") and b'"eClass"' in stripped:
        return False
    try:
        text = stripped.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return any(
        token in text
        for token in ("package ", "part def ", "requirement def ", "private import")
    ) or text.lstrip().startswith(("//", "standard library", "library package", "package"))


def parse_projects(payload: object) -> list[dict[str, str]]:
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    if not isinstance(payload, list):
        return []
    projects: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("@id") or item.get("id") or "")
        name = str(item.get("name") or "")
        if pid and name:
            projects.append({"id": pid, "name": name})
    return projects


def parse_manifest_documents(manifest: dict) -> list[tuple[str, str]]:
    mapping = manifest.get("documentIdsToName") or {}
    if not isinstance(mapping, dict):
        return []
    items = [(str(doc_id), str(name)) for doc_id, name in mapping.items()]
    items.sort(key=lambda item: item[1].lower())
    return items


def docker_missing_message() -> str:
    return (
        "Docker is not installed or not on PATH.\n"
        "SysON runs as a local web app in Docker. Install Docker Desktop once,\n"
        f"then start it and retry:\n  {DOCKER_DESKTOP_URL}\n"
        "On Windows, enable WSL 2 when the installer asks.\n"
        "When Docker Desktop shows 'Engine running', confirm with: docker version"
    )


def docker_not_running_message(detail: str) -> str:
    return (
        "Docker is installed but the engine is not running.\n"
        "Start Docker Desktop and wait until it reports that the engine is running,\n"
        f"then retry.\n  {detail}"
    )


# --- HTTP / Docker ------------------------------------------------------------


class HttpClient:
    def __init__(self, base: str, timeout: float = 60) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str, query: dict[str, str] | None = None) -> str:
        url = self.base + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        return url

    def request(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, bytes]:
        req = urllib.request.Request(
            self._url(path, query),
            data=data,
            headers=headers or {},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read() if exc.fp else b""
            raise SysonError(
                f"{method} {path} failed: HTTP {exc.code}\n{body.decode('utf-8', errors='replace')}"
            ) from exc
        except urllib.error.URLError as exc:
            raise SysonError(f"{method} {path} failed: {exc.reason}") from exc

    def json(
        self,
        method: str,
        path: str,
        *,
        payload: object | None = None,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> object:
        hdrs = {"Accept": "application/json", **(headers or {})}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        _status, body = self.request(method, path, data=data, headers=hdrs, query=query)
        if not body:
            return None
        text = body.decode("utf-8")
        stripped = text.lstrip()
        if stripped.startswith("<!DOCTYPE") or stripped.startswith("<html"):
            raise SysonError(
                f"{method} {path} returned the SysON web page, not JSON.\n"
                "The REST API is at /api/rest/projects."
            )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SysonError(
                f"{method} {path} returned non-JSON: {text[:200]!r}"
            ) from exc


def encode_multipart(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = "----DoqsSyson" + uuid.uuid4().hex
    buf = io.BytesIO()
    for name, value in fields.items():
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        buf.write(value.encode("utf-8"))
        buf.write(b"\r\n")
    for name, (filename, content, content_type) in files.items():
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'
            ).encode()
        )
        buf.write(f"Content-Type: {content_type}\r\n\r\n".encode())
        buf.write(content)
        buf.write(b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode())
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


def which_docker() -> str | None:
    return shutil.which("docker")


def docker_compose_cmd() -> list[str]:
    if not COMPOSE_FILE.is_file():
        raise SysonError(f"Compose file not found: {COMPOSE_FILE}")
    return [
        "docker",
        "compose",
        "-p",
        COMPOSE_PROJECT,
        "-f",
        str(COMPOSE_FILE),
    ]


def run_docker(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SysonError(detail or f"command failed: {' '.join(args)}")
    return result


def ensure_docker() -> None:
    if not which_docker():
        raise SysonError(docker_missing_message())
    probe = run_docker(["docker", "version"], check=False)
    if probe.returncode != 0:
        detail = (probe.stderr or probe.stdout or "docker version failed").strip()
        raise SysonError(docker_not_running_message(detail))


def compose_up() -> None:
    print("Starting SysON (Docker Compose)...")
    print("The first run downloads images and can take several minutes.")
    run_docker(docker_compose_cmd() + ["up", "-d"], capture=False)


def compose_down() -> None:
    print("Stopping SysON (Postgres data volume is kept)...")
    run_docker(docker_compose_cmd() + ["down"])


def compose_running() -> bool:
    result = run_docker(docker_compose_cmd() + ["ps", "-q"], check=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def rest_is_ready(url: str) -> bool:
    req = urllib.request.Request(
        url.rstrip("/") + "/api/rest/projects",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read()
        payload = json.loads(body.decode("utf-8"))
        return isinstance(payload, list)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return False


def wait_for_syson(url: str, timeout: int = WAIT_SECONDS) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if rest_is_ready(url):
            return
        time.sleep(2)
    raise SysonError(
        f"SysON did not become ready at {url} within {timeout}s.\n"
        "Check Docker Desktop and: docker ps"
    )


def ensure_server(url: str) -> None:
    if rest_is_ready(url):
        return
    ensure_docker()
    compose_up()
    wait_for_syson(url)


# --- SysON API ----------------------------------------------------------------


def list_projects(client: HttpClient) -> list[dict[str, str]]:
    payload = client.json("GET", "/api/rest/projects")
    return parse_projects(payload)


def create_project(client: HttpClient, name: str) -> dict[str, str]:
    payload = client.json("POST", "/api/rest/projects", query={"name": name})
    projects = parse_projects([payload] if isinstance(payload, dict) else payload or [])
    if projects:
        return projects[0]
    if isinstance(payload, dict):
        pid = str(payload.get("@id") or payload.get("id") or "")
        pname = str(payload.get("name") or name)
        if pid:
            return {"id": pid, "name": pname}
    raise SysonError(f"Could not create SysON project {name!r}: {payload!r}")


def find_project(projects: list[dict[str, str]], name: str) -> dict[str, str] | None:
    matches = [p for p in projects if p["name"] == name]
    if not matches:
        return None
    if len(matches) > 1:
        print(
            f"Warning: {len(matches)} projects named {name!r}; using {matches[0]['id']}"
        )
    return matches[0]


def fetch_editing_context_id(client: HttpClient, project_id: str) -> str:
    payload = client.json(
        "POST",
        GRAPHQL_ENDPOINT,
        payload={
            "query": FETCH_EDITING_CONTEXT_QUERY,
            "variables": {"projectId": project_id},
        },
    )
    if not isinstance(payload, dict):
        raise SysonError(f"Unexpected editing-context response: {payload!r}")
    if payload.get("errors"):
        raise SysonError(f"GraphQL error: {payload['errors']}")
    project = (
        (payload.get("data") or {}).get("viewer") or {}
    ).get("project") or {}
    editing = project.get("currentEditingContext") or {}
    editing_id = editing.get("id")
    if not editing_id:
        raise SysonError(f"No editing context for project {project_id}")
    return str(editing_id)


def import_sysml_file(
    client: HttpClient,
    file_path: Path,
    editing_context_id: str,
    upload_name: str,
) -> None:
    operations = {
        "query": UPLOAD_DOCUMENT_MUTATION,
        "variables": {
            "input": {
                "id": str(uuid.uuid4()),
                "editingContextId": editing_context_id,
                "file": None,
                "readOnly": False,
            }
        },
    }
    file_map = {"0": "variables.file"}
    body, content_type = encode_multipart(
        {
            "operations": json.dumps(operations),
            "map": json.dumps(file_map),
        },
        {
            "0": (
                upload_name,
                file_path.read_bytes(),
                "text/plain",
            )
        },
    )
    _status, raw = client.request(
        "POST",
        GRAPHQL_UPLOAD_ENDPOINT,
        data=body,
        headers={"Content-Type": content_type},
        timeout=120,
    )
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("errors"):
        raise SysonError(f"Import {upload_name} GraphQL error: {payload['errors']}")
    result = (payload.get("data") or {}).get("uploadDocument") or {}
    typename = result.get("__typename")
    if typename == "UploadDocumentSuccessPayload":
        print(f"Imported {upload_name}")
        report = result.get("report")
        if report:
            print(report)
        return
    if typename == "ErrorPayload":
        messages = result.get("messages") or []
        detail = "; ".join(
            f"{m.get('level', 'ERROR')}: {m.get('body', '')}" for m in messages
        )
        raise SysonError(f"Import {upload_name} failed: {detail or result}")
    raise SysonError(f"Import {upload_name} unexpected response: {payload}")


def list_documents(client: HttpClient, project_id: str) -> list[tuple[str, str]]:
    _status, raw = client.request(
        "GET",
        PROJECT_DOWNLOAD_ENDPOINT.format(project_id=project_id),
        timeout=120,
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        manifest_name = next(
            (name for name in archive.namelist() if name.endswith("/manifest.json")),
            None,
        )
        if not manifest_name:
            raise SysonError("Project archive has no manifest.json")
        with archive.open(manifest_name) as handle:
            manifest = json.load(io.TextIOWrapper(handle, encoding="utf-8"))
    return parse_manifest_documents(manifest)


def download_sysml_text(
    client: HttpClient,
    project_id: str,
    document_id: str,
) -> bytes:
    editing_id = fetch_editing_context_id(client, project_id)
    path = DOCUMENT_DOWNLOAD_ENDPOINT.format(
        editing_context_id=editing_id,
        document_id=document_id,
    )
    _status, body = client.request(
        "GET",
        path,
        headers={"Accept": "text/html"},
        timeout=120,
    )
    return body


def delete_project(client: HttpClient, project_id: str) -> None:
    try:
        client.request("DELETE", f"/api/rest/projects/{project_id}")
        return
    except SysonError:
        pass
    payload = client.json(
        "POST",
        GRAPHQL_ENDPOINT,
        payload={
            "query": DELETE_PROJECT_MUTATION,
            "variables": {
                "input": {
                    "id": str(uuid.uuid4()),
                    "projectId": project_id,
                }
            },
        },
    )
    if isinstance(payload, dict) and payload.get("errors"):
        raise SysonError(f"Could not delete project {project_id}: {payload['errors']}")


def project_edit_url(base: str, project_id: str) -> str:
    return f"{base.rstrip('/')}/projects/{project_id}/edit"


# --- Commands -----------------------------------------------------------------


def cmd_open(root: Path, url: str, name: str, open_browser: bool) -> None:
    ensure_server(url)
    client = HttpClient(url)
    projects = list_projects(client)
    existing = find_project(projects, name)
    files = collect_sysml(root)
    if existing:
        print(f"Project {name!r} already exists ({existing['id']}).")
        print("Diagrams from earlier sessions are kept. Use 'reload' to re-import from git.")
        project_id = existing["id"]
    else:
        created = create_project(client, name)
        project_id = created["id"]
        print(f"Created project {name!r} ({project_id}).")
        if not files:
            print(f"No architecture/*.sysml files found under {root}")
        else:
            editing_id = fetch_editing_context_id(client, project_id)
            rels = [path.relative_to(root) for path in files]
            for path in import_order(files):
                upload_name = document_name(path.relative_to(root), rels)
                import_sysml_file(client, path, editing_id, upload_name)
    edit = project_edit_url(url, project_id)
    print(f"SysON: {url}")
    print(f"Project: {edit}")
    print("Edit in the browser, then save back to git with:")
    print("  python doqs/scripts/syson.py save")
    if open_browser:
        webbrowser.open(edit)


def cmd_save(root: Path, url: str, name: str) -> None:
    ensure_server(url)
    client = HttpClient(url)
    existing = find_project(list_projects(client), name)
    if not existing:
        raise SysonError(
            f"No SysON project named {name!r}. Run: python doqs/scripts/syson.py open"
        )
    files = collect_sysml(root)
    documents = list_documents(client, existing["id"])
    if not documents:
        raise SysonError("Project has no documents to export.")
    written = 0
    for doc_id, doc_name in documents:
        if not doc_name.lower().endswith(".sysml"):
            print(f"Skipping {doc_name!r} (not a .sysml document; homepage zip is JSON).")
            continue
        target = path_for_document(doc_name, root, files)
        if target is None:
            if doc_name in DEFAULT_SKIP_DOCUMENTS:
                print(f"Skipping default SysON document {doc_name!r}.")
                continue
            extra = extra_export_path(root, doc_name)
            if extra is None:
                print(f"Skipping {doc_name!r}: no matching file under architecture/.")
                continue
            target = extra
            print(f"New document {doc_name!r} → {target.relative_to(root)}")
        content = download_sysml_text(client, existing["id"], doc_id)
        if not looks_like_textual_sysml(content):
            raise SysonError(
                f"Export of {doc_name!r} did not return textual SysML.\n"
                "In SysON, download from the explorer on a document named *.sysml,\n"
                "not Download on the homepage (that zip is JSON)."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        print(f"Wrote {target.relative_to(root)}")
        written += 1
    if written == 0:
        raise SysonError("Nothing was exported.")
    print(f"Saved {written} file(s). Review with git diff, then commit.")


def cmd_reload(root: Path, url: str, name: str, open_browser: bool) -> None:
    ensure_server(url)
    client = HttpClient(url)
    existing = find_project(list_projects(client), name)
    if existing:
        print(f"Deleting {name!r} (diagrams in this project will be lost)...")
        delete_project(client, existing["id"])
    cmd_open(root, url, name, open_browser)


def cmd_stop() -> None:
    ensure_docker()
    compose_down()
    print("Stopped. Run 'open' again to continue; diagrams remain in the Docker volume.")


def cmd_status(root: Path, url: str, name: str) -> None:
    docker_ok = which_docker() is not None
    print(f"Docker binary: {'yes' if docker_ok else 'no'}")
    if docker_ok:
        probe = run_docker(["docker", "version"], check=False)
        print(f"Docker engine: {'running' if probe.returncode == 0 else 'not running'}")
        print(f"Compose project {COMPOSE_PROJECT}: {'up' if compose_running() else 'down'}")
    print(f"Machine root: {root}")
    print(f"SysON project name: {name}")
    files = collect_sysml(root)
    print(f"SysML files: {len(files)}")
    for path in files:
        print(f"  {path.relative_to(root)}")
    if rest_is_ready(url):
        client = HttpClient(url)
        projects = list_projects(client)
        print(f"SysON at {url}: {len(projects)} project(s)")
        for project in projects:
            mark = " (this repo)" if project["name"] == name else ""
            print(f"  {project['name']}  {project['id']}{mark}")
    else:
        print(f"SysON at {url}: API not reachable")


def run_ui_command(command: str, root: Path, url: str, name: str) -> tuple[bool, str]:
    """Run a whitelist command and capture print() output for the control panel."""
    if command not in UI_COMMANDS:
        return False, f"Unknown command: {command}"
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            if command == "open":
                cmd_open(root, url, name, open_browser=True)
            elif command == "save":
                cmd_save(root, url, name)
            elif command == "reload":
                cmd_reload(root, url, name, open_browser=True)
            elif command == "stop":
                cmd_stop()
            elif command == "status":
                cmd_status(root, url, name)
        return True, buf.getvalue()
    except SysonError as exc:
        text = buf.getvalue()
        if text and not text.endswith("\n"):
            text += "\n"
        return False, text + str(exc)


def panel_response(
    method: str,
    path: str,
    *,
    root: Path,
    url: str,
    name: str,
) -> tuple[int, str, bytes]:
    """HTTP response for the control panel. Pure enough to unit-test."""
    parsed = urllib.parse.urlparse(path)
    route = parsed.path.rstrip("/") or "/"
    if method == "GET" and route in ("/", "/index.html"):
        if not PANEL_HTML.is_file():
            return 500, "text/plain; charset=utf-8", b"control-panel.html missing"
        html = PANEL_HTML.read_text(encoding="utf-8")
        return 200, "text/html; charset=utf-8", html.encode("utf-8")
    if method == "GET" and route == "/api/meta":
        payload = {"folder": root.name, "project": name, "root": str(root)}
        return 200, "application/json", json.dumps(payload).encode("utf-8")
    if method == "POST" and route.startswith("/run/"):
        command = route[len("/run/") :].strip("/")
        if command not in UI_COMMANDS:
            body = json.dumps({"ok": False, "output": f"Unknown command: {command}"})
            return 404, "application/json", body.encode("utf-8")
        ok, output = run_ui_command(command, root, url, name)
        body = json.dumps({"ok": ok, "output": output})
        return 200, "application/json", body.encode("utf-8")
    return 404, "text/plain; charset=utf-8", b"Not found"


def make_panel_handler(root: Path, url: str, name: str) -> type[BaseHTTPRequestHandler]:
    class PanelHandler(BaseHTTPRequestHandler):
        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            status, ctype, body = panel_response(
                "GET", self.path, root=root, url=url, name=name
            )
            self._send(status, ctype, body)

        def do_POST(self) -> None:  # noqa: N802
            status, ctype, body = panel_response(
                "POST", self.path, root=root, url=url, name=name
            )
            self._send(status, ctype, body)

        def log_message(self, fmt: str, *args: object) -> None:
            print(f"[panel] {fmt % args}")

    return PanelHandler


def cmd_ui(root: Path, url: str, name: str, open_browser: bool) -> None:
    if not PANEL_HTML.is_file():
        raise SysonError(f"Control panel HTML missing: {PANEL_HTML}")
    handler = make_panel_handler(root, url, name)
    try:
        server = ThreadingHTTPServer((PANEL_HOST, PANEL_PORT), handler)
    except OSError as exc:
        raise SysonError(
            f"Could not bind {PANEL_HOST}:{PANEL_PORT} ({exc}).\n"
            "Is the control panel already running?"
        ) from exc
    panel_url = f"http://{PANEL_HOST}:{PANEL_PORT}/"
    print(f"SysON control panel: {panel_url}")
    print(f"Machine: {root.name}  ·  project: {name}")
    print("This is the control panel, not the SysON editor.")
    print("Close this window (or Ctrl+C) to quit the panel.")
    if open_browser:
        webbrowser.open(panel_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped control panel.")
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run Eclipse SysON against architecture/*.sysml in a DOQS machine repo."
        )
    )
    parser.add_argument(
        "command",
        choices=("open", "save", "reload", "stop", "status", "ui"),
        help="ui: browser control panel. open: start + import if needed. save: export .sysml. "
        "reload: re-import from git (drops diagrams). stop: compose down. status: summary.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Machine repo root (default: cwd if it looks like a machine, else parent of doqs/)",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"SysON base URL (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="SysON project name (default: okh.toml name)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser (open/reload/ui)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "stop":
            cmd_stop()
            return 0
        root = args.root.resolve() if args.root else default_machine_root()
        name = args.name or project_name(root)
        if args.command == "ui":
            cmd_ui(root, args.url, name, not args.no_browser)
        elif args.command == "open":
            cmd_open(root, args.url, name, not args.no_browser)
        elif args.command == "save":
            cmd_save(root, args.url, name)
        elif args.command == "reload":
            cmd_reload(root, args.url, name, not args.no_browser)
        elif args.command == "status":
            cmd_status(root, args.url, name)
        return 0
    except SysonError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
