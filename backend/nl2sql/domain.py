"""Immutable contracts shared across application and provider boundaries."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scalar = str | int | bool | None
Bind = str | int
Row = dict[str, Scalar]
Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")]


class FrozenModel(BaseModel):
    """External data rejects extra keys and cannot mutate after validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Failure(Exception):
    """Safe application failure; details never contain raw provider errors."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class Principal(FrozenModel):
    """Server-owned, current data and metadata entitlements."""

    id: str
    tenant: str
    regions: tuple[str, ...]
    metrics: tuple[str, ...]
    policy_version: str = "synthetic-policy-v1"
    scopes: tuple[str, ...] = ()


class Column(FrozenModel):
    """Physical column approved for local compilation."""

    name: Identifier
    kind: Literal["text", "integer", "decimal", "date"]
    physical_name: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[^\x00]+$"
    )
    description: str = Field(default="", max_length=4000)
    precision: int | None = Field(default=None, ge=1, le=38)
    scale: int | None = Field(default=None, ge=-84, le=127)


class Table(FrozenModel):
    """Physical object with a declared unique native grain."""

    id: Identifier
    columns: tuple[Column, ...]
    grain: tuple[Identifier, ...]
    physical_owner: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[^\x00]+$"
    )
    physical_name: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[^\x00]+$"
    )
    tenant_column: Identifier | None = "tenant_id"
    description: str = Field(default="", max_length=4000)


class LogicalJoinEvidence(FrozenModel):
    """A proposed logical join remains subject to signed physical/business/security review."""

    review_reference: str = Field(min_length=1, max_length=200)
    effective_catalog_version: str
    source_grain: tuple[Identifier, ...]
    target_grain: tuple[Identifier, ...]
    partition_pairs: tuple[tuple[Identifier, Identifier], ...]
    column_types: tuple[tuple[str, str], ...]
    evidence: str = Field(min_length=1, max_length=4000)


class Relation(FrozenModel):
    """Verified composite relationship; direction describes safe fact traversal."""

    id: Identifier
    left: Identifier
    right: Identifier
    pairs: tuple[tuple[Identifier, Identifier], ...]
    cardinality: Literal["many_to_one", "one_to_one", "one_to_many", "many_to_many"]
    certified: bool = True
    temporal: Literal["static", "current_only"] = "static"
    evidence: str = "Previously certified synthetic relationship"
    physical_key_id: str | None = None
    logical_evidence: LogicalJoinEvidence | None = None


class Dimension(FrozenModel):
    """Governed field ID mapped to one physical column."""

    id: Identifier
    table: Identifier
    column: Identifier
    kind: Literal["text", "integer", "decimal", "date"]
    entity: bool = False


class MetricExpression(FrozenModel):
    """Only catalog stewards define formulas; the model selects their stable metric IDs."""

    kind: Literal["difference", "ratio"]
    numerator: Identifier
    denominator: Identifier


class Metric(FrozenModel):
    """Certified aggregate; monetary sums retain integer minor-unit precision."""

    id: Identifier
    label: str
    aliases: tuple[str, ...]
    domain: Identifier
    table: Identifier
    column: Identifier
    aggregate: Literal["sum", "count", "avg", "min", "max"]
    unit: Annotated[str, Field(pattern=r"^(?:[A-Z]{3}|count|percent)$")]
    scale: int = Field(default=1, ge=1, le=1_000_000_000)
    decimal_places: int = Field(default=2, ge=0, le=12)
    temporal: Literal["snapshot", "current", "event"]
    definition: str
    expression: MetricExpression | None = None


class ScopePolicy(FrozenModel):
    """Certified mappings, never guessed from discovered column names."""

    strategy: Literal["tenant_scope", "database_context"] = "tenant_scope"
    tenant_column: Identifier | None = "tenant_id"
    scope_dimension: Identifier | None = "region_id"
    scope_claim: Literal["regions", "scopes"] = "regions"
    status_column: Identifier | None = "status"
    evidence: str = "Legacy synthetic scope contract"


class EntityMapping(FrozenModel):
    """Exact lookup with an explicit, direct tenant/scope policy on the entity table."""

    id: Identifier = "customer"
    fields: tuple[Identifier, ...] = ("customer", "customer_id")
    canonical_field: Identifier = "customer_id"
    table: Identifier = "customers"
    key_column: Identifier = "customer_id"
    label_columns: tuple[Identifier, ...] = ("name", "alias")
    tenant_column: Identifier = "tenant_id"
    scope_column: Identifier = "region_id"
    scope_claim: Literal["regions", "scopes"] = "regions"


class SemanticView(FrozenModel):
    """Certified logical view; multi-fact combinations require explicit component contracts."""

    id: Identifier
    version: str
    domain: Identifier
    root: Identifier
    grain: tuple[Identifier, ...]
    metrics: tuple[Identifier, ...]
    dimensions: tuple[Identifier, ...]
    relationships: tuple[Identifier, ...]
    time_column: Identifier | None = None
    time_kind: Literal["snapshot", "event"] = "snapshot"
    components: tuple[Identifier, ...] = ()
    mandatory_status: str = "active"
    certified: bool = True
    evidence: str
    policy: ScopePolicy | None = None
    common_key: Identifier = "customer_id"


def view_policy(view: SemanticView) -> ScopePolicy:
    """Compatibility for pinned V4.2 fixtures; new Oracle certification requires explicit policy."""
    return view.policy or ScopePolicy(status_column=None if view.components else "status")


def scope_values(policy: ScopePolicy, principal: Principal) -> tuple[str, ...]:
    """Server-owned scope claims; model text cannot choose a different principal."""
    return tuple(sorted(principal.regions if policy.scope_claim == "regions" else principal.scopes))


class Catalog(FrozenModel):
    """Single authority for physical, business, temporal and policy metadata."""

    version: str
    approved: bool
    effective_from: date
    effective_to: date
    default_as_of: date
    fiscal_start_month: int | None = Field(default=None, ge=1, le=12)
    tables: tuple[Table, ...]
    relations: tuple[Relation, ...]
    dimensions: tuple[Dimension, ...]
    metrics: tuple[Metric, ...]
    views: tuple[SemanticView, ...]
    entities: tuple[EntityMapping, ...] = (EntityMapping(),)
    classification: Literal["synthetic", "restricted"] = "restricted"
    policy_version: str = "synthetic-policy-v1"
    templates: tuple["ReportTemplate", ...] = ()


class TypedValue(FrozenModel):
    """Tagged filter value; coercion is explicitly checked by plan validation."""

    kind: Literal["text", "integer", "date", "decimal", "text_list", "null"]
    value: (
        Annotated[str, Field(max_length=200)]
        | Annotated[int, Field(ge=-(2**63), le=2**63 - 1)]
        | tuple[Annotated[str, Field(max_length=200)], ...]
        | None
    )


class Predicate(FrozenModel):
    """Bound predicate referencing a stable field ID."""

    field: Identifier
    op: Literal["eq", "ne", "gt", "ge", "lt", "le", "in", "is_null", "is_not_null"]
    value: TypedValue


class FilterGroup(FrozenModel):
    """Bounded nested boolean expression; never contains SQL text."""

    op: Literal["and", "or"]
    children: tuple["Predicate | FilterGroup", ...] = Field(min_length=1, max_length=20)


class Sort(FrozenModel):
    """Output field sort with stable tie-breakers applied by the compiler."""

    field: Identifier
    direction: Literal["asc", "desc"] = "asc"


class Period(FrozenModel):
    """Snapshot as-of dates cannot be aggregated over time."""

    kind: Literal["as_of"] = "as_of"
    as_of: date


class DateRange(FrozenModel):
    """Half-open business-date interval, preserving event versus snapshot semantics."""

    kind: Literal["range"] = "range"
    start: date
    end_exclusive: date

    @model_validator(mode="after")
    def ordered(self) -> "DateRange":
        """Never silently swap or widen invalid boundaries."""
        if self.start >= self.end_exclusive:
            raise ValueError("Range start must precede its exclusive end")
        return self


class FiscalPeriod(FrozenModel):
    """Year identifies the start year in the catalog's explicitly approved fiscal calendar."""

    kind: Literal["fiscal_year"] = "fiscal_year"
    year: int = Field(ge=1900, le=2200)


class Ranking(FrozenModel):
    """Rank approved aggregates within selected dimensions, after aggregation."""

    metric: Identifier
    partition_by: tuple[Identifier, ...] = ()
    method: Literal["row_number", "dense_rank"] = "row_number"
    direction: Literal["asc", "desc"] = "desc"
    top_n: int = Field(ge=1, le=1000, strict=True)


class QueryPlan(FrozenModel):
    """Model-selectable DSL; identity, SQL, joins and timeouts are server-owned."""

    schema_version: Literal["1.0"] = "1.0"
    catalog_version: str
    view_id: Identifier
    view_version: str = "1.0.0"
    metrics: tuple[Identifier, ...] = Field(min_length=1, max_length=5)
    dimensions: tuple[Identifier, ...] = Field(default=(), max_length=5)
    filters: Predicate | FilterGroup | None = None
    having: Predicate | FilterGroup | None = None
    period: Period | DateRange | FiscalPeriod | None = None
    sort: tuple[Sort, ...] = Field(default=(), max_length=5)
    limit: int = Field(default=100, ge=1, le=1000, strict=True)
    operation: Literal["aggregate", "preaggregate", "combine"] = "aggregate"
    ranking: Ranking | None = None

    @model_validator(mode="after")
    def unique_fields(self) -> "QueryPlan":
        """Duplicate output aliases would otherwise overwrite result values."""
        if len(set(self.metrics + self.dimensions)) != len(self.metrics + self.dimensions):
            raise ValueError("Output fields must be unique")
        return self


class ReportTemplate(FrozenModel):
    """New approved exact reports are metadata changes, not Python rewrites."""

    id: Identifier
    question: str = Field(min_length=1, max_length=4000)
    plan: QueryPlan


class Proof(FrozenModel):
    """Server-generated semantic and authorization proof."""

    catalog_digest: str
    principal_digest: str
    view_id: str
    view_version: str
    relationships: tuple[str, ...]
    tables: tuple[str, ...]
    grain: tuple[str, ...]


class ValidatedPlan(FrozenModel):
    """Plan with resolved immutable semantics, scoped to current principal."""

    plan: QueryPlan
    proof: Proof


class CompiledQuery(FrozenModel):
    """Compiler output is a draft until independently validated."""

    sql: str
    binds: tuple[tuple[str, Bind], ...]
    bind_types: tuple[tuple[str, Literal["text", "integer", "decimal", "date"]], ...] = ()
    dialect: Literal["sqlite", "oracle"]
    validated_plan: ValidatedPlan
    output: tuple[str, ...]
    compiler_version: Literal["1.0"] = "1.0"
    bundle_version: str = ""


class Capability(FrozenModel):
    """Short-lived signed authority; fabricated or altered instances cannot execute."""

    query: CompiledQuery
    expires_at: float
    signature: str


class ExecutionResult(FrozenModel):
    """Actual bounded database results with honest truncation metadata."""

    rows: tuple[Row, ...]
    truncated: bool
    duration_ms: float


class Provenance(FrozenModel):
    """Safe business-level provenance, separate from physical schema and binds."""

    catalog_version: str
    query_reference: str
    reporting_as_of: date | None
    reporting_range: tuple[date, date] | None = None
    source_refresh_at: datetime | None = None
    freshness_status: Literal["unknown"] = "unknown"
    executed_at: datetime
    units: dict[str, str]
    truncated: bool
    route: Literal["template", "model", "followup"]
    bundle_version: str = ""


class Answer(FrozenModel):
    """Internal result contract mapped separately to the existing EWS interface."""

    session_id: str
    status: Literal["completed", "empty", "clarification_required", "unsupported"]
    message: str
    rows: tuple[Row, ...] = ()
    provenance: Provenance | None = None


def money_text(value: int | str, scale: int, decimal_places: int = 2) -> str:
    """Avoid binary floats when serializing financial aggregates."""
    return format(Decimal(value) / Decimal(scale), f".{decimal_places}f")


Catalog.model_rebuild()
