# candor-blocks

Typed caveat blocks for data products, following [CANDID core](https://github.com/edtrochim/candid_core)'s five categories, with one addition: every guard says what enforces it.

A block is a YAML file holding a data product's caveats and definitions. A `dataset` block describes the whole product; a narrower block (one source, one table, one estimator) holds only what differs from it and takes the rest from `dataset`.

```yaml
schema: candor-blocks/0.1
id: ga_dor
name: Georgia DOR timber values
suitability_and_limitations:
  application_limitations:
    - id: nominal_county_grain
      statement: The table prints 159 county rows but only a few distinct price zones.
      guard: Count price zones, not counties.
      enforcement: applied            # applied | flagged | advisory
      enforced_by: ["dbt:model.timber_prices.v_public_prices"]
      tested_by: ["dbt:test.timber_prices.assert_ga_dor_one_row_per_zone"]
context_and_definitions:
  key_term_definitions:
    sawtimber:
      definition: Softwood trees 9.0 in. DBH and larger.
      defined_by: USDA Forest Service FIA
      thresholds: [{field: DIA, op: ">=", value: 9.0, unit: in}]
```

## What it adds to CANDID core

- **Field names, categories and required fields are CANDID core's own**, checked against its published field list (`candid-core-fields.json`, vendored at commit `471193e`). Unknown fields are rejected, so a block can't drift from the standard.
- **Types.** CANDID core describes its fields but doesn't type them. Here a limitation is `{id, statement, guard, enforcement, enforced_by, flag_column}`, and a term is `{definition, defined_by, thresholds}`.
- **Enforcement.** A guard is `applied` when the producer's code already obeys it, `flagged` when the producer marks the affected rows in `flag_column`, or `advisory` when nothing can check it. `applied` and `flagged` guards name their code in `enforced_by` (`py:module:attribute` or `dbt:<unique_id>`) and, in `tested_by`, a test that fails when the guard is broken (a dbt singular test, or `pytest:<path>::<test>`). `candor-blocks check` fails when either is missing, and the build's own test run checks that each test passes. Consumers act on flags and read only the guards nothing enforces in the artifact they read: an `applied` guard holds only for readers of what its `enforced_by` names.
- **Defining authority and thresholds.** A term names the body that defines it, and where its definition is a set of thresholds, it lists them in machine-readable form.

## Use

```bash
candor-blocks check candor/ --dbt-manifest target/manifest.json   # validate, exit 1 on problems (--root for pytest: paths)
candor-blocks schema                                              # JSON Schema of a block
```

```python
from candor_blocks import load_blocks, resolve, flags, advisory, dump, parse

blocks = load_blocks(Path("candor"))
block = resolve(blocks, "ga_dor")          # with the dataset block's caveats folded in
flags(block, row)                          # the flagged guards that apply to one row
advisory(block, reads="dbt:model.x.v_view")  # the guards a reader of that artifact has to read
document = dump(blocks)                    # JSON to ship with the data; parse() reads it back
```
