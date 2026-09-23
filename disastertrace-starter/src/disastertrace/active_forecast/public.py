"""Model-visible value-track DTOs; private lineage and certificates stay offline."""

from typing import Annotated, Literal

from pydantic import BeforeValidator

from .core import Evaluator
from .schema import (
    Episode,
    Exact,
    Instant,
    Name,
    Nonnegative,
    PixelCounts,
    Positive,
    StrictModel,
    Support,
    Target,
    as_tuple,
)


class PublicIndex(StrictModel):
    entity: Name
    variable: Name
    unit: Name
    support: Support
    version: Name


class PublicRecord(PublicIndex):
    quality: Literal["valid", "missing", "invalid"]
    value: Exact | PixelCounts | None


class CatalogCard(StrictModel):
    id: Name
    cost: Positive
    title: Name
    issued_at: Instant | None
    issue_label: Name
    record_index: Annotated[tuple[PublicIndex, ...], BeforeValidator(as_tuple)]


class EvidenceCard(StrictModel):
    id: Name
    records: Annotated[tuple[PublicRecord, ...], BeforeValidator(as_tuple)]


class PublicView(StrictModel):
    schema_version: Literal["active_forecast.public.v1"] = "active_forecast.public.v1"
    representation: Literal["exact_product_values"] = "exact_product_values"
    question: Name
    target: Target
    time_policy: Literal["archive_delivery", "historical_asof"]
    as_of: Instant | None
    catalog_complete: Literal[True] = True
    catalog: Annotated[tuple[CatalogCard, ...], BeforeValidator(as_tuple)]
    evidence: Annotated[tuple[EvidenceCard, ...], BeforeValidator(as_tuple)]
    remaining_budget: Nonnegative
    rules: tuple[str, ...] = (
        "The catalog lists the complete eligible pool and record scopes, not unread values or quality.",
        "Unobserved or invalid values are unknown, never zero or negative.",
        "Compare only the fixed entity, variable, unit, support and requested versions.",
        "revision_delta: both exact versions must be valid; yes iff after-before >= threshold.",
        "count_threshold: lower=valid exceedances; upper=all supports-valid nonexceedances.",
        "area_threshold: lower=positive/(height*width); upper=1-negative/(height*width).",
        "For count/area: yes if lower >= threshold, no if upper < threshold, else unknown.",
        "Numbers n/d are exact rationals. Missing pixels stay in the full denominator.",
        "Certify the complete-pool decision; local unknown may require further reading.",
        "Cite only acquired cards sufficient to establish the decision; catalog absence may suffice.",
        "Return exactly {decision: yes|no|unknown, citations: [acquired card IDs]} as JSON.",
    )


def public_view(episode: Episode, read_ids, budget: int) -> PublicView:
    evaluator = Evaluator(episode)
    ids, spent = evaluator.checked_budget(read_ids, budget)
    catalog, evidence = [], []
    for card in evaluator.cards.values():
        indices = tuple(
            PublicIndex(
                entity=r.entity,
                variable=r.variable,
                unit=r.unit,
                support=r.support,
                version=r.version,
            )
            for r in card.records
        )
        catalog.append(
            CatalogCard(
                id=card.id,
                cost=card.cost,
                title=card.title,
                issued_at=card.issued_at,
                issue_label=card.issue_label,
                record_index=indices,
            )
        )
        if card.id in ids:
            records = tuple(
                PublicRecord(**index.model_dump(), quality=r.quality, value=r.value)
                for index, r in zip(indices, card.records)
            )
            evidence.append(EvidenceCard(id=card.id, records=records))
    return PublicView(
        question=episode.question,
        target=episode.target,
        time_policy=episode.time_policy,
        as_of=episode.as_of,
        catalog=tuple(catalog),
        evidence=tuple(evidence),
        remaining_budget=budget - spent,
    )
