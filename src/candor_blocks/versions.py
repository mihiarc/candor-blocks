"""Every schema version candor-blocks has published, and the steps that bring a block written in
an older one up to the current one. A step fills nothing its old version had no way to say: a
field the old version lacked stays unset, so a reader sees that the block doesn't say."""

from collections.abc import Callable, Mapping

from candor_blocks.schema import SCHEMA


def _from_0_1(block: dict) -> dict:
    """0.2 adds `publisher`. A 0.1 block had no field for one, so it stays unset."""
    if "publisher" in block:
        raise ValueError(f"{block.get('id')!r}: candor-blocks/0.1 has no publisher field")
    return block | {"schema": "candor-blocks/0.2", "publisher": None}


# Each published version before the current one, oldest first, with the step to the next.
_STEPS: dict[str, Callable[[dict], dict]] = {
    "candor-blocks/0.1": _from_0_1,
}
VERSIONS = (*_STEPS, SCHEMA)


def _number(version: str) -> tuple[int, ...] | None:
    prefix, _, number = version.partition("/")
    parts = number.split(".")
    return tuple(map(int, parts)) if prefix == "candor-blocks" and all(p.isdigit() for p in parts) else None


def readable(version: object, where: str) -> str:
    """`version` if this candor-blocks reads it. A newer version raises: what its fields mean
    can't be known here."""
    if version in VERSIONS:
        return version
    number = _number(version) if isinstance(version, str) else None
    if number is not None and number > _number(SCHEMA):
        raise ValueError(f"{where} is written in {version}, newer than this candor-blocks reads "
                         f"(through {SCHEMA}); upgrade candor-blocks to read it")
    raise ValueError(f"{where} names schema {version!r}, which candor-blocks never published "
                     f"(it published {', '.join(VERSIONS)})")


def upgrade(block: Mapping, version: str) -> dict:
    """`block`, written in `version`, brought one step at a time to the current schema."""
    if block.get("schema") != version:
        raise ValueError(f"block {block.get('id')!r} is written in {block.get('schema')!r}, its document in {version}")
    current = dict(block)
    for old in VERSIONS[VERSIONS.index(version):-1]:
        current = _STEPS[old](current)
    return current
