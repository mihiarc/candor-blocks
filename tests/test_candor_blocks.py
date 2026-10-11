import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from candor_blocks import Block, Limitation, dump, flags, load_blocks, parse, problems, resolve
from candor_blocks.schema import CATEGORIES, candid_core_fields, category_key

BLOCKS = Path(__file__).parent / "blocks"


def test_models_hold_exactly_candid_cores_fields():
    official = {(category_key(f["category"]), f["field_name"]) for f in candid_core_fields()}
    ours = {(key, name) for key, model in CATEGORIES.items() for name in model.model_fields}
    assert ours == official


def test_a_renamed_field_is_rejected():
    with pytest.raises(ValidationError, match="ethics_and_bias"):
        Block.model_validate({"schema": "candor-blocks/0.1", "id": "x", "name": "x",
                              "context_and_definitions": {"ethics_and_bias": ["drifted"]}})


@pytest.mark.parametrize("fields", [
    {"enforcement": "applied"},
    {"enforcement": "advisory", "enforced_by": ["py:json:dumps"]},
    {"enforcement": "flagged", "enforced_by": ["py:json:dumps"]},
    {"enforcement": "applied", "enforced_by": ["py:json:dumps"], "flag_column": "x"},
    {"enforcement": "applied", "enforced_by": ["json.dumps"]},
])
def test_a_guard_says_truthfully_what_enforces_it(fields):
    with pytest.raises(ValidationError):
        Limitation(id="g", statement="s", guard="g", **fields)


def test_blocks_load_by_file_name():
    assert set(load_blocks(BLOCKS)) == {"dataset", "source_a"}


def test_a_block_takes_what_it_leaves_out_from_the_dataset_block():
    block = resolve(load_blocks(BLOCKS), "source_a")
    limitations = {x.id: x for x in block.suitability_and_limitations.application_limitations}
    assert set(limitations) == {"one_grain", "lower_bound", "zones"}
    assert limitations["lower_bound"].statement.startswith("Source A's")
    assert block.suitability_and_limitations.suitability_summary == "One state's county prices."
    assert block.suitability_and_limitations.known_gaps == ["No 2022 edition.", "No 2023 edition."]
    assert set(block.context_and_definitions.key_term_definitions) == {"sawtimber", "price_zone"}
    assert block.lifecycle_and_access.support_status == "Active."


def test_complete_blocks_with_real_targets_have_no_problems(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"nodes": {"model.prices.v_prices": {}}}))
    assert problems(load_blocks(BLOCKS), dbt_manifest=manifest) == []


def test_problems_name_empty_required_fields_and_missing_targets(tmp_path: Path):
    blocks = load_blocks(BLOCKS)
    blocks["dataset"].lifecycle_and_access.breaking_changes = []
    blocks["dataset"].suitability_and_limitations.application_limitations[0].enforced_by = ["py:json:nope"]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"nodes": {}}))
    found = problems(blocks, dbt_manifest=manifest)
    assert "dataset: lifecycle_and_access.breaking_changes is required by CANDID core and is empty" in found
    assert "dataset.one_grain: py:json:nope does not import" in found
    assert "source_a.lower_bound: dbt:model.prices.v_prices is not in the dbt manifest" in found


def test_flags_name_the_guards_a_row_falls_under():
    block = resolve(load_blocks(BLOCKS), "source_a")
    assert [f.guard for f in flags(block, {"is_lower_bound": True})] == ["source_a.lower_bound"]
    assert flags(block, {"is_lower_bound": False}) == []


def test_a_document_round_trips():
    blocks = load_blocks(BLOCKS)
    assert parse(json.loads(json.dumps(dump(blocks)))) == blocks
