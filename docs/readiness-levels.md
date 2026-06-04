# OTRL and ODRL (readiness levels)

DOQS machine modules declare maturity in `okh.toml` using OKH-LOSH fields:

```toml
technology-readiness-level = "OTRL-3"
documentation-readiness-level = "ODRL-2"
```

These are **not** NASA TRLs and **not** the unrelated W3C “ODRL” rights language. They are the **Open Technology Readiness Level (OTRL)** and **Open Documentation Readiness Level (ODRL)** from the IOP Alliance [Open Know-How](https://github.com/iop-alliance/OpenKnowHow) ontology.

Authoritative source in this repo: [`spec/otrl.ttl`](../spec/otrl.ttl) (from `OpenKnowHow/src/spec/otrl.ttl`).

## OTRL — Open Technology Readiness Level

| Level | Label | Summary goal |
|-------|--------|----------------|
| **OTRL-1** | Ideation | Product idea; needs identified; initial specifications defined |
| **OTRL-2** | Conception | Mature product concept formulated |
| **OTRL-3** | Development | Product model developed |
| **OTRL-4** | Prototyping and testing | Full functional prototype built and tested |
| **OTRL-5** | Manufacturing development | Fairly reliable processes identified and characterized |
| **OTRL-6** | Product qualification | Conformity assessment or comparable certification |

Stages are **metadata** on a module at a point in time — not a Git branch. A design that advances from OTRL-3 to OTRL-4 keeps the same repo; update the field and version tag as appropriate.

## ODRL — Open Documentation Readiness Level

| Level | Label | Summary goal |
|-------|--------|----------------|
| **ODRL-1** | Documentation process commenced | Published information under free/open licence |
| **ODRL-2** | Collaborative documentation in progress | Documentation in editable formats enabling collaboration |
| **ODRL-3** | Full documentation published | Complete documentation per DIN SPEC 3105-1; stable release |
| **ODRL-3\*** | Full documentation published & audited | Public evidence of documentation maturity (e.g. DIN SPEC 3105-2, OSHWA) |
| **ODRL-4** | Full documentation for product qualification | Qualification docs for decentralized commercial distribution |

## How to choose levels

- Set levels honestly per module — sub-modules can differ from the machine root.
- **Documentation** lagging behind hardware is common early on (e.g. OTRL-3 / ODRL-2).
- Do not bump OTRL because a CAD file exists unless the corresponding prototype/test goal is met.

## References

- [Open Know-How repository](https://github.com/iop-alliance/OpenKnowHow)
- [OKH-LOSH](https://github.com/OPEN-NEXT/OKH-LOSH) — manifest fields `technology-readiness-level`, `documentation-readiness-level`
- DIN SPEC 3105 (technical documentation for open-source hardware)
