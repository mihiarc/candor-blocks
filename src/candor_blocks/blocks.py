"""Load, combine, check and serialize candor blocks."""

import importlib
import json
from collections.abc import Mapping
from importlib.resources.abc import Traversable
from pathlib import Path

import yaml
from pydantic import BaseModel

from candor_blocks.schema import CANDID_CORE_COMMIT, CATEGORIES, SCHEMA, Block, Limitation, candid_core_fields, category_key


class Flag(BaseModel):
    """A flagged limitation that applies to one row: cite `guard`, report `statement`."""

    guard: str
    statement: str


def load_blocks(directory: Path | Traversable) -> dict[str, Block]:
    """Every `*.yaml` block in `directory`, keyed by id. Each file is named for its block's id,
    and the `dataset` block lives in `_dataset.yaml`."""
    blocks = {}
    for path in sorted(directory.iterdir(), key=lambda p: p.name):
        if not path.name.endswith(".yaml"):
            continue
        block = Block.model_validate(yaml.safe_load(path.read_text()))
        if block.id != path.name.removesuffix(".yaml").lstrip("_"):
            raise ValueError(f"{path.name} holds block {block.id!r}; name the file for its id")
        blocks[block.id] = block
    if "dataset" not in blocks:
        raise ValueError(f"no dataset block (_dataset.yaml) in {directory}")
    return blocks


def resolve(blocks: Mapping[str, Block], block_id: str) -> Block:
    """Block `block_id` with what it leaves out taken from the dataset block. Lists and term
    maps combine, a limitation replaces the dataset's limitation with the same id, and text
    the block sets replaces the dataset's."""
    dataset, block = blocks["dataset"], blocks[block_id]
    merged: dict = {"schema": SCHEMA, "id": block.id, "name": block.name}
    for key in CATEGORIES:
        base, own = getattr(dataset, key), getattr(block, key)
        fields = {}
        for name in type(base).model_fields:
            a, b = getattr(base, name), getattr(own, name)
            if name == "application_limitations":
                fields[name] = [x for x in a if x.id not in {y.id for y in b}] + b
            elif isinstance(a, list):
                fields[name] = a + [x for x in b if x not in a]
            elif isinstance(a, dict):
                fields[name] = {**a, **b}
            else:
                fields[name] = b if b is not None else a
        merged[key] = fields
    return Block.model_validate(merged)


def problems(blocks: Mapping[str, Block], *, dbt_manifest: Path | None = None, root: Path = Path(".")) -> list[str]:
    """What keeps the blocks from being complete and true: fields CANDID core requires that
    the dataset block (and so every block combined with it) leaves empty, and `enforced_by`
    or `tested_by` targets that don't exist. `py:` targets are imported, so check them in the
    environment that ships the code; `dbt:` targets are looked up in `dbt_manifest`; `pytest:`
    paths are relative to `root`. Whether each test passes is the build's own test run."""
    found = []
    dataset = blocks["dataset"]
    for field in candid_core_fields():
        key = category_key(field["category"])
        if field.get("required") and not getattr(getattr(dataset, key), field["field_name"]):
            found.append(f"dataset: {key}.{field['field_name']} is required by CANDID core and is empty")
    nodes = set(json.loads(dbt_manifest.read_text())["nodes"]) if dbt_manifest else None
    for block_id, block in blocks.items():
        for limitation in block.suitability_and_limitations.application_limitations:
            for target in limitation.enforced_by + limitation.tested_by:
                if why := _missing(target, nodes, root):
                    found.append(f"{block_id}.{limitation.id}: {why}")
    return found


def _missing(target: str, nodes: set[str] | None, root: Path) -> str | None:
    kind, _, ref = target.partition(":")
    if kind == "pytest":
        path, _, name = ref.partition("::")
        source = root / path
        if not source.is_file() or f"def {name}(" not in source.read_text():
            return f"{target} is not a test in {root.resolve()}"
        return None
    if kind == "dbt":
        if nodes is None:
            return f"{target} needs a dbt manifest to check"
        return None if ref in nodes else f"{target} is not in the dbt manifest"
    module, _, attribute = ref.partition(":")
    try:
        found = importlib.import_module(module)
        for part in attribute.split("."):
            found = getattr(found, part)
    except (ImportError, AttributeError):
        return f"{target} does not import"
    return None


def flags(block: Block, row: Mapping[str, object]) -> list[Flag]:
    """The flagged limitations that apply to one row of data. Pass a resolved block, so the
    dataset's limitations count too."""
    return [
        Flag(guard=f"{block.id}.{limitation.id}", statement=limitation.statement)
        for limitation in block.suitability_and_limitations.application_limitations
        if limitation.flag_column and row.get(limitation.flag_column)
    ]


def advisory(block: Block, reads: str | None = None) -> list[Limitation]:
    """The limitations a consumer has to read and follow. An `applied` or `flagged` guard holds
    only in the artifact that enforces it, so pass `reads` (the `enforced_by` target of the
    view, model or function the consumer actually reads) and every guard whose enforcement
    lives elsewhere comes back too. Without `reads`, only `advisory` guards come back."""
    return [
        x
        for x in block.suitability_and_limitations.application_limitations
        if x.enforcement == "advisory" or (reads is not None and reads not in x.enforced_by)
    ]


def dump(blocks: Mapping[str, Block]) -> dict:
    """The blocks as one JSON-ready document, the form a producer ships with its data."""
    return {
        "schema": SCHEMA,
        "candid_core": f"github.com/edtrochim/candid_core@{CANDID_CORE_COMMIT}",
        "blocks": {k: b.model_dump(mode="json", by_alias=True, exclude_defaults=True) for k, b in blocks.items()},
    }


def parse(document: Mapping) -> dict[str, Block]:
    """Blocks from a document written by `dump`."""
    if document.get("schema") != SCHEMA:
        raise ValueError(f"expected schema {SCHEMA!r}, got {document.get('schema')!r}")
    return {k: Block.model_validate(v) for k, v in document["blocks"].items()}
