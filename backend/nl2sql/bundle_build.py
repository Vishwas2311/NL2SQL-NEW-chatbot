"""Build and validate mutually compatible catalog, graph, search and compiler mappings."""

import json
import secrets
import time
from dataclasses import dataclass, field

from nl2sql.catalog import JoinGraph, catalog_hash, digest, validate_catalog
from nl2sql.compiler import Compiler
from nl2sql.config import RetrievalOptions
from nl2sql.domain import Catalog, Failure, Period, Principal, QueryPlan
from nl2sql.drift import policy_digest
from nl2sql.metadata_store import BundleArtifacts
from nl2sql.physical import PhysicalInventory, inventory_digest
from nl2sql.planning import PlanValidator
from nl2sql.retrieval import EmbeddingProvider, Retriever, search_records
from nl2sql.security import SQLValidator
from nl2sql.vector_index import VectorIndexFactory


def grant_digest(principals: tuple[Principal, ...]) -> str:
    """Changes to data or metric grants are part of the version contract."""
    return digest(
        json.dumps(
            [item.model_dump(mode="json") for item in sorted(principals, key=lambda user: user.id)],
            sort_keys=True,
        )
    )


@dataclass
class BundleBuilder:
    """No model is called while discovering or rebuilding metadata."""

    encoder: EmbeddingProvider | None = None
    encoder_version: str | None = None
    builds: int = 0
    vector_factory: VectorIndexFactory | None = None
    retrieval_options: RetrievalOptions = field(default_factory=RetrievalOptions)

    def search_fingerprint(self, catalog: Catalog, principals: tuple[Principal, ...]) -> str:
        """Search tuning and encoder compatibility are versioned with the certified corpus."""
        return digest(
            json.dumps(
                {
                    "documents": search_records(catalog),
                    "grants": grant_digest(principals),
                    "encoder": self.encoder_version,
                    "options": self.retrieval_options.model_dump(),
                    "vector_backend": "faiss-flat-ip" if self.vector_factory else "exact-cosine",
                },
                sort_keys=True,
            )
        )

    def build(
        self,
        catalog: Catalog,
        inventory: PhysicalInventory,
        principals: tuple[Principal, ...],
        previous: BundleArtifacts | None = None,
    ) -> BundleArtifacts:
        """New unmapped physical objects do not trigger a lexical/vector/graph rebuild."""
        started = time.perf_counter()
        catalog = catalog.model_copy(update={"approved": True})
        if (
            len(catalog.tables) > 10_000
            or len(catalog.metrics) > 10_000
            or len(catalog.relations) > 50_000
            or sum(len(table.columns) for table in catalog.tables) > 100_000
            or len({tuple(sorted(user.metrics)) for user in principals}) > 128
        ):
            raise Failure("BUNDLE_LIMIT", "Metadata bundle exceeds its approved build budget.", 413)
        validate_catalog(catalog)
        if any(user.policy_version != catalog.policy_version for user in principals):
            raise Failure(
                "POLICY_VERSION", "Principal grants must match the certified policy revision.", 409
            )
        if self.encoder is not None and not self.encoder_version:
            raise ValueError("An approved embedding model version must be supplied")
        fingerprint = catalog_hash(catalog)
        graph = JoinGraph(catalog)
        graph_fingerprint = digest(json.dumps(list(graph.graph.edges(data=True)), sort_keys=True))
        policy_fingerprint = policy_digest(catalog)
        compiler_fingerprint = digest(fingerprint + ":compiler-v43-1:plan-1.0")
        search_fingerprint = self.search_fingerprint(catalog, principals)
        if (
            previous is not None
            and previous.catalog_digest == fingerprint
            and previous.search_digest == search_fingerprint
        ):
            if (
                previous.graph_digest != graph_fingerprint
                or previous.policy_digest != policy_fingerprint
                or previous.compiler_digest != compiler_fingerprint
                or previous.encoder_version != self.encoder_version
                or (self.encoder is None and previous.vector_digest is not None)
            ):
                raise Failure(
                    "METADATA_INTEGRITY", "Metadata component fingerprints disagree.", 503
                )
            return previous.model_copy(
                update={
                    "physical_digest": inventory_digest(inventory),
                    "build_ms": (time.perf_counter() - started) * 1000,
                    "rebuilt": (),
                }
            )
        if len(json.dumps(search_records(catalog)).encode()) > 10_000_000:
            raise Failure("BUNDLE_LIMIT", "Search metadata exceeds its byte budget.", 413)
        unknown = {key for user in principals for key in user.metrics} - {
            metric.id for metric in catalog.metrics
        }
        if len({user.id for user in principals}) != len(principals):
            raise Failure(
                "GRANT_MAPPING", "Duplicate principal grant identities are not allowed.", 409
            )
        if unknown:
            raise Failure(
                "GRANT_MAPPING", "A configured grant references an unavailable metric.", 409
            )
        planner = PlanValidator(catalog)
        compiler = Compiler(catalog, planner)
        validator = SQLValidator(catalog, secrets.token_bytes(32))
        # This identity performs compilation-only structural checks, never data reads or approvals.
        contract = Principal(
            id="compile-contract-only",
            tenant="validation",
            regions=("validation",),
            scopes=("validation",),
            metrics=tuple(metric.id for metric in catalog.metrics),
        )
        dialect = "oracle" if inventory.source_kind == "oracle" else "sqlite"
        for view in catalog.views:
            metrics = view.metrics[:5] if view.components else view.metrics[:1]
            plan = QueryPlan(
                catalog_version=catalog.version,
                view_id=view.id,
                view_version=view.version,
                metrics=metrics,
                dimensions=view.dimensions[:1],
                operation="combine" if view.components else "aggregate",
                period=Period(as_of=catalog.default_as_of) if view.time_kind == "event" else None,
            )
            query = compiler.compile(planner.validate(plan, contract), contract, dialect)
            validator.validate(query, contract, time.time() + 30)
        search = Retriever(
            catalog, principals, self.encoder, self.vector_factory, self.retrieval_options
        )
        try:
            vector = (
                digest(json.dumps(search.vector_manifest(), sort_keys=True))
                if self.encoder is not None
                else None
            )
        finally:
            search.close()
        self.builds += 1
        return BundleArtifacts(
            catalog_digest=fingerprint,
            physical_digest=inventory_digest(inventory),
            graph_digest=graph_fingerprint,
            search_digest=search_fingerprint,
            policy_digest=policy_fingerprint,
            compiler_digest=compiler_fingerprint,
            encoder_version=self.encoder_version,
            vector_digest=vector,
            build_ms=(time.perf_counter() - started) * 1000,
            rebuilt=(
                "catalog",
                "graph",
                "bm25",
                "compiler",
                "validator",
                *(("vectors",) if vector else ()),
            ),
        )
