import json
import shutil
from pathlib import Path

import pytest

from candor_blocks import SCHEMA, VERSIONS, dump, load_blocks, parse, problems, resolve

FIXTURES = Path(__file__).parent / "versions"


def fixture(version: str) -> Path:
    return FIXTURES / version.removeprefix("candor-blocks/")


def test_every_published_version_has_a_fixture():
    assert {p.name for p in FIXTURES.iterdir()} == {fixture(v).name for v in VERSIONS}


@pytest.mark.parametrize("version", VERSIONS)
def test_a_document_in_each_published_version_reads_into_the_current_model(version):
    document = parse(json.loads((fixture(version) / "document.json").read_text()))
    folder = load_blocks(fixture(version) / "blocks")
    assert document == folder
    assert document.written_in == folder.written_in == version
    for block_id, block in document.items():
        assert block.schema_ == SCHEMA
        assert resolve(document, block_id).schema_ == SCHEMA


def test_an_upgraded_block_says_only_what_its_producer_said():
    old = parse(json.loads((fixture("candor-blocks/0.1") / "document.json").read_text()))
    new = parse(json.loads((fixture("candor-blocks/0.2") / "document.json").read_text()))
    assert old == {k: b.model_copy(update={"publisher": None}) for k, b in new.items()}
    assert [resolve(old, k).publisher for k in old] == [None, None]


@pytest.mark.parametrize("version", ["candor-blocks/0.3", "candor-blocks/1.0", "candor-blocks/0.2.1"])
def test_a_document_newer_than_this_library_says_to_upgrade_it(version):
    with pytest.raises(ValueError, match=f"written in {version}, newer .* upgrade candor-blocks"):
        parse({"schema": version, "blocks": {"dataset": {"schema": version, "id": "dataset", "name": "x"}}})


@pytest.mark.parametrize("version", [None, "candor-blocks/0.0", "candor-blocks/0.1.5", "other/1.0", "candor-blocks/x"])
def test_a_version_never_published_is_refused(version):
    with pytest.raises(ValueError, match="never published"):
        parse({"schema": version, "blocks": {}})


def test_a_block_written_in_another_version_than_its_document_is_refused():
    with pytest.raises(ValueError, match="'dataset' is written in 'candor-blocks/0.2', its document in candor-blocks/0.1"):
        parse({"schema": "candor-blocks/0.1", "blocks": {"dataset": {"schema": SCHEMA, "id": "dataset", "name": "x"}}})


def test_a_01_block_naming_a_publisher_is_refused():
    block = {"schema": "candor-blocks/0.1", "id": "dataset", "name": "x", "publisher": "Someone"}
    with pytest.raises(ValueError, match="0.1 has no publisher"):
        parse({"schema": "candor-blocks/0.1", "blocks": {"dataset": block}})


def test_a_folder_moves_to_a_new_version_together(tmp_path: Path):
    shutil.copy(fixture("candor-blocks/0.1") / "blocks" / "_dataset.yaml", tmp_path)
    shutil.copy(fixture("candor-blocks/0.2") / "blocks" / "basin_counts.yaml", tmp_path)
    with pytest.raises(ValueError, match="written in candor-blocks/0.1, candor-blocks/0.2"):
        load_blocks(tmp_path)


def test_a_producer_writes_the_current_version():
    old = load_blocks(fixture("candor-blocks/0.1") / "blocks")
    with pytest.raises(ValueError, match="move them to candor-blocks/0.2 before shipping"):
        dump(old)
    assert f"the blocks are written in candor-blocks/0.1; move them to {SCHEMA}" in problems(old)
    assert dump(load_blocks(fixture(SCHEMA) / "blocks"))["schema"] == SCHEMA
