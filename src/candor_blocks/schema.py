"""Typed CANDID core blocks.

Field names, categories and required fields follow CANDID core's published field list
(`candid-core-fields.json`, vendored from github.com/edtrochim/candid_core at
`CANDID_CORE_COMMIT`). CANDID core names and describes its fields but gives them no types;
the types here, and the structure of `Limitation` and `Term`, are this package's.
"""

import json
from importlib.resources import files
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA = "candor-blocks/0.2"
CANDID_CORE_COMMIT = "471193e"

Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+$")]
# `py:module:attribute` names a Python object; `dbt:<unique_id>` names a node in a dbt manifest.
Target = Annotated[str, StringConstraints(pattern=r"^(py:[\w.]+:[\w.]+|dbt:[\w.]+)$")]
# A test that fails when the guard is broken: a dbt singular test, or `pytest:<path>::<test name>`.
Test = Annotated[str, StringConstraints(pattern=r"^(dbt:test\.[\w.]+|pytest:[\w./-]+\.py::\w+)$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Limitation(_Model):
    """A caveat on using the data: what is true, what to do about it, and who makes sure.

    - `applied`: the producer's own code applies the guard, so a consumer cannot break it
      (a view already grouped to the grain the guard asks for, an estimator that never
      returns the forbidden figure). `enforced_by` names that code.
    - `flagged`: the producer marks every row the statement applies to with a true value in
      `flag_column`. `enforced_by` names the code that sets it.
    - `advisory`: no code can check it. A consumer has to read and follow the guard.

    An `applied` or `flagged` guard also names, in `tested_by`, a test that fails when the
    guard is broken, so the claim is checked on every build and not only asserted.
    """

    id: Id
    statement: str
    guard: str
    enforcement: Literal["applied", "flagged", "advisory"]
    enforced_by: list[Target] = []
    tested_by: list[Test] = []
    flag_column: str | None = None

    @model_validator(mode="after")
    def _enforcement_is_named(self) -> "Limitation":
        if self.enforcement == "advisory" and (self.enforced_by or self.tested_by or self.flag_column):
            raise ValueError(f"{self.id}: an advisory guard names no enforced_by, tested_by or flag_column")
        if self.enforcement != "advisory" and not (self.enforced_by and self.tested_by):
            raise ValueError(f"{self.id}: an {self.enforcement} guard names its enforced_by and tested_by")
        if (self.enforcement == "flagged") != (self.flag_column is not None):
            raise ValueError(f"{self.id}: flag_column goes with, and only with, a flagged guard")
        return self


class Threshold(_Model):
    """One atomized condition of a definition, on an attribute of the producer's own data."""

    field: str
    op: Literal["==", "!=", "<", "<=", ">", ">=", "in", "not_in"]
    value: float | int | str | list[float | int | str]
    unit: str | None = None


class Term(_Model):
    """A key term: what it means, which body defines it, and, where the definition is a set
    of thresholds, those thresholds (all of which hold together)."""

    definition: str
    defined_by: str
    thresholds: list[Threshold] = []


class SuitabilityAndLimitations(_Model):
    suitability_summary: str | None = None
    application_limitations: list[Limitation] = []
    data_quality_metrics: list[str] = []
    known_gaps: list[str] = []


class ContextAndDefinitions(_Model):
    key_term_definitions: dict[str, Term] = {}
    methodology_summary: str | None = None
    ethics_bias: list[str] = []
    vibes_social_context: str | None = None


class UseCasesAndTargetUsers(_Model):
    target_audience: list[str] = []
    recommended_expertise: str | None = None
    suggested_uses: list[str] = []
    key_instructions: list[str] = []
    example_teaching_resources: list[str] = []
    example_community_resources: list[str] = []
    example_apps: list[str] = []
    example_api_functions: list[str] = []
    example_art: list[str] = []
    example_games: list[str] = []


class ProvenanceAndRelationships(_Model):
    review_method: str | None = None
    candid_core_curation_method: str | None = None
    derived_datasets: list[str] = []
    linked_datasets: list[str] = []
    related_datasets: list[str] = []
    competitor_datasets: list[str] = []
    comparison_notes: str | None = None


class LifecycleAndAccess(_Model):
    support_status: str | None = None
    curation_update_philosophy: str | None = None
    changelog: list[str] = []
    breaking_changes: list[str] = []
    data_access_providers: list[str] = []
    user_feedback_channel: str | None = None
    carbon_energy_cost: str | None = None


CATEGORIES: dict[str, type[_Model]] = {
    "suitability_and_limitations": SuitabilityAndLimitations,
    "context_and_definitions": ContextAndDefinitions,
    "use_cases_and_target_users": UseCasesAndTargetUsers,
    "provenance_and_relationships": ProvenanceAndRelationships,
    "lifecycle_and_access": LifecycleAndAccess,
}


class Block(_Model):
    """One candor block. The `dataset` block describes a whole data product; a narrower block
    (a source, a table, an estimator) holds only what differs from it.

    `id`, `name` and `publisher` are this package's, not CANDID core fields. `publisher` names
    the body that publishes the data the block describes, such as the agency behind a source."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal["candor-blocks/0.2"] = Field(alias="schema")
    id: Id
    name: str
    publisher: str | None = None
    suitability_and_limitations: SuitabilityAndLimitations = SuitabilityAndLimitations()
    context_and_definitions: ContextAndDefinitions = ContextAndDefinitions()
    use_cases_and_target_users: UseCasesAndTargetUsers = UseCasesAndTargetUsers()
    provenance_and_relationships: ProvenanceAndRelationships = ProvenanceAndRelationships()
    lifecycle_and_access: LifecycleAndAccess = LifecycleAndAccess()


def candid_core_fields() -> list[dict]:
    """CANDID core's published field list: field_name, category, description, required."""
    return json.loads(files("candor_blocks").joinpath("candid-core-fields.json").read_text())["fields"]


def category_key(category: str) -> str:
    """'Suitability & Limitations' -> 'suitability_and_limitations'."""
    return category.lower().replace(" & ", "_and_").replace(" ", "_")
