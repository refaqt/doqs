# ADR-006 — Money leaves the bill of materials

- **Date:** 2026-09-18
- **Status:** Accepted
- **Changes:** [ADR-001 naming and versioning](2026-06-04_naming-and-versioning.md),
  [ADR-003 product families](2026-09-15_product-family-variants.md)
- **Breaking:** yes. See *Migration*.

## Context

The bill-of-materials header has sixteen fixed columns, and every validator
reads it exactly:

```
id,name,spec,category,qty,unit,unit_cost_eur,unit_mass_g,equiv_class,
supplier_1,supplier_1_pn,supplier_2,supplier_2_pn,supplier_3,supplier_3_pn,notes
```

Seven of them are commercial: the price, and three distributor slots each with a
part number. They sit in a design file, in a design history.

That causes three problems.

**A price change becomes a design commit.** Prices move weekly and designs move
rarely. Either the design history fills with price noise, or — what actually
happens — nobody updates the numbers and they quietly go stale while people keep
trusting them.

**One price cell is usually wrong.** Price depends on quantity, date, country
and customer. A single number in euros cannot be right for more than one order.

**It mixes two jobs.** "What is inside this machine" is a design question with a
long-lived answer. "What does it cost" is a commercial question with an answer
that expires. One file cannot serve both.

## Decision

**The bill of materials answers "what is inside". A separate application answers
"what does it cost".**

### 1. What stays and what leaves

| Stays — design data | Leaves — commercial data |
| --- | --- |
| what it is, how many, which unit | price, and any price break |
| brand and brand part number | distributor, distributor part number |
| mass | lead time, stock, minimum order |
| the interchange tag, `equiv_class` | currency and date |

The brand part number stays because it identifies a physical object. The
distributor part number leaves because it identifies a commercial relationship.

### 2. The new header — twelve columns

```
id,name,spec,category,qty,unit,unit_mass_g,equiv_class,brand,brand_pn,part,notes
```

`part` is the reference into a parts library, `stoq:hiwin/hgr-rail#HGR20R500`.
When it is filled, `brand` and `brand_pn` are read from the library and
validation checks they agree with what you wrote. When the item is not in a
library, you write them yourself and `part` stays empty.

### 3. One identifier is what doqs owes the pricing system

doqs exports what is inside and how many. Something else multiplies that by
whatever prices are true today — a supplier interface, a spreadsheet, a
purchasing system. Neither side has to know how the other works, and the whole
join is one column: `part`, or `brand` plus `brand_pn` where there is no library
entry.

That is the entire integration contract. Writing it down is the reason this is a
decision record and not a cleanup.

### 4. Libraries are technical too

A library's `bom/parts.csv` carries no price and no distributor either, for the
same reason. It also has a side benefit: prices are the most catalogue-like data
a supplier holds, so leaving them out reduces what ADR-004 has to worry about
when it decides what may be committed.

## Consequences

- A price update never touches a design repository again.
- `unit_cost_eur` disappears, and with it the assumption that everything is
  bought in euros.
- Anyone who wants a costed list runs the machine-wide purchase list through
  their own pricing source. doqs does not ship that tool and should not.
- Four fewer columns to fill in by hand on every row.
- The second and third supplier slots were often empty and always a guess about
  how many alternatives a row could have. `equiv_class` already says "these are
  interchangeable" without limiting the count to three.

## Migration

This breaks every existing `bom.csv`. The change is mechanical and should land
on its own, in its own pull request, so the diff stays readable.

1. Update `BOM_HEADERS` in `scripts/naming_rules.py` to the twelve columns.
2. `validate_names.py` reports the old sixteen-column header with a message
   naming this record, so the fix is obvious rather than puzzling.
3. Rewrite the fixture bill-of-materials files under `tests/fixtures/`.
4. Drop the four columns from `resolve_bom.py` and `aggregate_bom.py`.
5. Note it in `CONTRIBUTING.md`, and in `docs/naming.md` beside the column list.

A machine repository migrates by deleting seven columns and adding three. The
prices it deletes are almost certainly out of date, which is the argument.

## Alternatives rejected

| Alternative | Why not |
| --- | --- |
| Keep the columns and leave them empty | The header is validated exactly, so empty commercial columns stay on every row forever, inviting someone to fill them in again. |
| Keep the price, drop only the distributors | The price is the value that changes fastest. Keeping it keeps the problem. |
| Move prices to a sidecar file in the same repository | Same repository, same history, same noise. It only moves the file. |
| Keep prices for quoting | A quote needs today's price for a real quantity. A number committed months ago is worse than no number, because it looks authoritative. |
