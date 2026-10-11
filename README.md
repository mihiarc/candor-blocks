# candor-blocks

Honest, checkable fine print for datasets.

Every dataset has fine print. A price table might repeat the same few numbers across hundreds of counties. A series might stop in 2022. Prices after 2019 might run low because some sales were recorded without their values. This fine print usually sits in a PDF or a footnote, and two things go wrong:

- People, and the AI tools that answer questions from data, miss it.
- Nobody can tell which warnings the data already takes care of and which ones the reader still has to act on.

candor-blocks is a small Python tool for writing that fine print in a structured file that travels with the data. Each warning says what is true, what to do about it, and who makes sure it happens:

- **Handled.** The data producer's own processing already takes care of it.
- **Marked.** The producer marks every affected row, so readers can see exactly which rows it touches.
- **Up to the reader.** Nothing can check it automatically, so the reader has to follow it.

A warning marked "handled" or "marked" also names a test that fails if that stops being true, so the promise is checked every time the data is rebuilt.

A warning is only handled in the place that handles it. If a summary table already groups counties into price zones, someone reading the summary is covered; someone reading the raw county table is not. So a tool reading the data says which table it reads, and gets back exactly the warnings it still has to follow.

## Where it comes from

The fields follow [CANDID core](https://github.com/edtrochim/candid_core), Erin Trochim's framework for "data candor": telling users plainly what a dataset is good for, where it falls short, and what its terms mean. candor-blocks uses CANDID core's categories and field names as published, and adds the record of who makes sure each warning is followed.

It was developed alongside the Data Foundation's [Semantic Commons for Climate, Nature & Economy](https://datafoundation.org/pages/semantic-commons-for-climate-nature-economy-cne), an initiative to give climate, nature and economic data shared definitions, so data from different sources can be compared and combined with confidence.

## What a file looks like

One file per dataset, or per source within it. This one describes a state's published timber prices:

```yaml
schema: candor-blocks/0.2
id: ga_dor
name: Georgia DOR timber values
publisher: Georgia Department of Revenue

suitability_and_limitations:
  application_limitations:
    # Handled: the summary table already groups counties into price zones.
    - id: nominal_county_grain
      statement: The table prints 159 county rows but only a few distinct price zones.
      guard: Count price zones, not counties.
      enforcement: applied
      enforced_by: ["dbt:model.prices.v_comparable"]
      tested_by: ["dbt:test.prices.assert_one_row_per_zone"]
    # Marked: every affected row carries no_volume_weights = true.
    - id: no_volume_weights
      statement: DOR publishes its prices without the volumes behind them.
      guard: Don't volume-weight flagged rows against other sources.
      enforcement: flagged
      enforced_by: ["dbt:model.prices.v_comparable"]
      tested_by: ["dbt:test.prices.assert_flag_no_volume_weights"]
      flag_column: no_volume_weights
    # Up to the reader: no code can check this one.
    - id: missing_2022
      statement: The 2022 table was never captured.
      guard: Don't read 2022 change from the surrounding years.
      enforcement: advisory

context_and_definitions:
  key_term_definitions:
    # A term says what it means, who defines it, and, where it can, the exact cutoffs.
    sawtimber:
      definition: Softwood trees 9.0 in. DBH and larger.
      defined_by: USDA Forest Service FIA
      thresholds:
        - {field: species_group, op: "==", value: softwood}
        - {field: DIA, op: ">=", value: 9.0, unit: in}
```

`statement` is what is true, `guard` is what to do about it, and `enforcement` is who makes sure: `applied` (handled), `flagged` (marked) or `advisory` (up to the reader).

## For developers

Python 3.11 or later. Not on PyPI yet:

```bash
uv add git+https://github.com/mihiarc/candor-blocks@v0.2.0
# or
pip install git+https://github.com/mihiarc/candor-blocks@v0.2.0
```

**Write blocks.** Keep one folder per data product. `_dataset.yaml` holds the `dataset` block, which describes the whole product and fills every field CANDID core requires. Each narrower block (a source, a table, an estimator) is a file named for its `id`, and holds only what differs from the dataset block.

```text
candor/
  _dataset.yaml
  ga_dor.yaml
```

**Check them.**

```bash
candor-blocks check candor/ --dbt-manifest target/manifest.json --root .
candor-blocks schema    # the JSON Schema of a block, for editors and other languages
```

`check` lists each problem and exits 1 when a block doesn't validate, a file isn't named for its block, the dataset block leaves a required CANDID core field empty, or something named in `enforced_by` or `tested_by` doesn't exist.

- `enforced_by` names code: `py:module:attribute`, or `dbt:<unique_id>` from a dbt manifest. `py:` targets are imported, so run `check` in the environment that ships the code.
- `tested_by` names a test that fails when the guard breaks: a dbt test (`dbt:test.<project>.<name>`) or `pytest:<path>::<test>`, with paths starting from `--root`. Your build's own test run confirms each one passes.

**Read them.**

```python
from pathlib import Path

from candor_blocks import advisory, dump, flags, load_blocks, parse, resolve

blocks = load_blocks(Path("candor"))
block = resolve(blocks, "ga_dor")  # with the dataset block's caveats folded in

# The marked warnings one row falls under, each with its id and statement.
flags(block, {"zone": "3", "price_per_ton": 41.2, "no_volume_weights": True})
# -> [Flag(guard='ga_dor.no_volume_weights', statement='DOR publishes its prices ...')]

# The warnings a reader still has to follow, given the table it reads.
advisory(block, reads="dbt:model.prices.v_comparable")  # ga_dor's: missing_2022
advisory(block, reads="dbt:model.prices.v_counties")    # ga_dor's: all three

# One JSON document to ship beside the data. parse() reads it back.
document = dump(blocks)
assert parse(document) == blocks
```

`resolve` folds the dataset block into a narrower one: lists and term maps combine, a limitation replaces the dataset's limitation with the same `id`, and text the block sets replaces the dataset's.

**Relation to CANDID core.** Categories, field names and required fields come from CANDID core's published field list, vendored at commit `471193e`, and unknown fields are rejected, so a block can't drift from the standard. CANDID core describes its fields without giving them types. candor-blocks types them: a limitation is `{id, statement, guard, enforcement, enforced_by, tested_by, flag_column}`, and a term is `{definition, defined_by, thresholds}`. A block's `id`, `name` and `publisher` sit outside CANDID core's categories; `publisher` names the body that publishes the data, and a narrower block that leaves it out takes the dataset block's.

**Versions.** The schema is `candor-blocks/0.2`. Each block names its schema version, and `parse` refuses a document written for another one.

## License

[Apache License 2.0](LICENSE). `src/candor_blocks/candid-core-fields.json` is CANDID core's field list, copyright 2025 Erin Trochim, used under the MIT license in `candid-core-fields.LICENSE` beside it; [NOTICE](NOTICE) records the attribution.
