"""Typed CANDID core caveat blocks whose guards say what enforces them."""

from candor_blocks.blocks import Flag, advisory, dump, flags, load_blocks, parse, problems, resolve
from candor_blocks.schema import CANDID_CORE_COMMIT, SCHEMA, Block, Limitation, Term, Threshold

__all__ = [
    "CANDID_CORE_COMMIT",
    "SCHEMA",
    "Block",
    "Flag",
    "Limitation",
    "Term",
    "Threshold",
    "advisory",
    "dump",
    "flags",
    "load_blocks",
    "parse",
    "problems",
    "resolve",
]
