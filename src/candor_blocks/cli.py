"""`candor-blocks check DIR [--dbt-manifest PATH]` and `candor-blocks schema`."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from candor_blocks.blocks import load_blocks, problems
from candor_blocks.schema import Block


def main() -> None:
    parser = argparse.ArgumentParser(prog="candor-blocks", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="validate a folder of blocks and their enforcement targets")
    check.add_argument("directory", type=Path)
    check.add_argument("--dbt-manifest", type=Path, help="target/manifest.json, to check dbt: targets")
    commands.add_parser("schema", help="print the JSON Schema of a block")
    args = parser.parse_args()
    if args.command == "schema":
        print(json.dumps(Block.model_json_schema(by_alias=True), indent=2))
        return
    try:
        found = problems(load_blocks(args.directory), dbt_manifest=args.dbt_manifest)
    except (ValidationError, ValueError) as error:
        found = [str(error)]
    for problem in found:
        print(problem, file=sys.stderr)
    sys.exit(1 if found else 0)
