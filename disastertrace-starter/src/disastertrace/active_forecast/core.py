"""Exact evidence entailment and private ex-post certificate enumeration."""

from fractions import Fraction
from itertools import combinations
from typing import Annotated

from pydantic import BeforeValidator, ValidationError

from .schema import (
    Answer,
    CountTarget,
    Decision,
    Episode,
    Exact,
    Name,
    Nonnegative,
    RevisionTarget,
    StrictModel,
    as_tuple,
    compatible,
    eligible,
)


def powerset(ids):
    for size in range(len(ids) + 1):
        yield from combinations(ids, size)


class Reference(StrictModel):
    decision: Decision
    reason: str
    value: Exact | None = None
    lower: Exact | None = None
    upper: Exact | None = None


class Certificate(StrictModel):
    ids: Annotated[tuple[Name, ...], BeforeValidator(as_tuple)]
    cost: Nonnegative


class Certificates(StrictModel):
    minimal_sets: Annotated[tuple[Certificate, ...], BeforeValidator(as_tuple)]
    minimum_cost: Nonnegative
    oracle_access: str = (
        "private complete pool; ex-post certificate lower bound, not an online controller"
    )


class Score(StrictModel):
    valid: bool
    goal_correct: bool
    visible_decision_correct: bool
    grounded_success: bool
    cited_only_read: bool
    read_sufficient: bool
    goal_decision: Decision
    visible_decision: Decision
    spent: Nonnegative
    minimum_extra_cost: Nonnegative
    budget_resolvable: bool
    avoidable_unresolved: bool
    supported_but_incomplete: bool


class Evaluator:
    """One immutable task; no model, source IO, mutable carrier or outcome access."""

    def __init__(self, episode: Episode):
        self.episode = Episode.model_validate(episode)
        self.cards = {
            c.id: c
            for c in self.episode.cards
            if eligible(c, self.episode.time_policy, self.episode.as_of, self.episode.delivery_step)
        }
        self.legal_ids = tuple(self.cards)
        self.target = self.episode.target
        self._records = {
            c.id: tuple(r for r in c.records if compatible(r, self.target))
            for c in self.cards.values()
        }
        self._reference_cache = {}
        self._sufficiency_cache = {}
        self._certificates = None

    def checked_reads(self, read_ids):
        if isinstance(read_ids, (str, bytes, dict)):
            raise ValueError("read IDs must be a collection of unique strings")  # noqa: TRY004
        ids = tuple(read_ids)
        if any(not isinstance(x, str) for x in ids) or len(ids) != len(set(ids)):
            raise ValueError("read IDs must be unique strings")
        if not set(ids).issubset(self.cards):
            raise ValueError("read contains an unavailable card")
        return frozenset(ids)

    def checked_budget(self, read_ids, budget):
        if type(budget) is not int or budget < 0:
            raise ValueError("budget must be a nonnegative integer")
        ids = self.checked_reads(read_ids)
        spent = sum(self.cards[x].cost for x in ids)
        if spent > budget:
            raise ValueError("read budget exceeded")
        return ids, spent

    def records(self, ids):
        return tuple(r for ident in self.legal_ids if ident in ids for r in self._records[ident])

    def reference(self, read_ids) -> Reference:
        ids = self.checked_reads(read_ids)
        if ids in self._reference_cache:
            return self._reference_cache[ids]
        target, records = self.target, self.records(ids)
        if isinstance(target, RevisionTarget):
            values = {r.version: r.value for r in records if r.quality == "valid"}
            if set(values) != set(target.versions):
                result = Reference(decision="unknown", reason="unread_or_absent_required_version")
            else:
                before, after = (values[v] for v in target.versions)
                delta = after - before
                result = Reference(
                    decision="yes" if delta >= target.threshold else "no",
                    reason="supported",
                    value=delta,
                )
        else:
            valid = [r for r in records if r.quality == "valid"]
            if isinstance(target, CountTarget):
                lower = Fraction(sum(r.value >= target.value_threshold for r in valid))
                upper = Fraction(
                    len(target.supports) - sum(r.value < target.value_threshold for r in valid)
                )
                threshold, reason = target.count_threshold, "insufficient_support"
            else:
                lower = Fraction(sum(r.value.positive for r in valid), target.total_pixels)
                upper = Fraction(
                    target.total_pixels - sum(r.value.negative for r in valid), target.total_pixels
                )
                threshold, reason = target.fraction_threshold, "incomplete_coverage"
            decision = "yes" if lower >= threshold else "no" if upper < threshold else "unknown"
            result = Reference(
                decision=decision,
                reason="supported" if decision != "unknown" else reason,
                lower=lower,
                upper=upper,
            )
        self._reference_cache[ids] = result
        return result

    def sufficient(self, read_ids) -> bool:
        ids = self.checked_reads(read_ids)
        if ids in self._sufficiency_cache:
            return self._sufficiency_cache[ids]
        goal, visible = self.reference(self.legal_ids), self.reference(ids)
        if goal.decision != "unknown":
            result = visible.decision == goal.decision
        elif visible.decision != "unknown":
            result = False
        else:
            all_records, read_records = self.records(self.legal_ids), self.records(ids)
            if isinstance(self.target, RevisionTarget):
                available = {r.version for r in all_records}
                invalid = {r.version for r in read_records if r.quality != "valid"}
                result = any(v not in available or v in invalid for v in self.target.versions)
            else:
                unread = {r.support.key for r in all_records} - {
                    r.support.key for r in read_records
                }
                if isinstance(self.target, CountTarget):
                    mass, threshold = len(unread), self.target.count_threshold
                else:
                    mass = Fraction(
                        sum(s.size for s in self.target.supports if s.key in unread),
                        self.target.total_pixels,
                    )
                    threshold = self.target.fraction_threshold
                # Catalog scope is known; values/quality of unread cards are not.
                result = visible.lower + mass < threshold and visible.upper - mass >= threshold
        self._sufficiency_cache[ids] = bool(result)
        return bool(result)

    def certificates(self) -> Certificates:
        if self._certificates is None:
            minimal = []
            for ids in powerset(self.legal_ids):
                if any(set(item.ids).issubset(ids) for item in minimal):
                    continue
                if self.sufficient(ids):
                    minimal.append(Certificate(ids=ids, cost=sum(self.cards[x].cost for x in ids)))
            if not minimal:
                raise ValueError("full eligible pool must have a certificate")
            self._certificates = Certificates(
                minimal_sets=tuple(minimal), minimum_cost=min(c.cost for c in minimal)
            )
        return self._certificates

    def extension_cost(self, read_ids) -> int:
        ids = self.checked_reads(read_ids)
        return min(
            sum(self.cards[x].cost for x in c.ids if x not in ids)
            for c in self.certificates().minimal_sets
        )

    def score(self, read_ids, answer, budget: int) -> Score:
        ids, spent = self.checked_budget(read_ids, budget)
        try:
            parsed = Answer.model_validate(answer)
        except ValidationError:
            parsed = None
        goal, visible = self.reference(self.legal_ids), self.reference(ids)
        access = parsed is not None and set(parsed.citations).issubset(ids)
        correct = parsed is not None and parsed.decision == goal.decision
        grounded = access and correct and self.sufficient(parsed.citations)
        extra = self.extension_cost(ids)
        return Score(
            valid=parsed is not None,
            goal_correct=correct,
            visible_decision_correct=parsed is not None and parsed.decision == visible.decision,
            grounded_success=bool(grounded),
            cited_only_read=access,
            read_sufficient=self.sufficient(ids),
            goal_decision=goal.decision,
            visible_decision=visible.decision,
            spent=spent,
            minimum_extra_cost=extra,
            budget_resolvable=extra <= budget - spent,
            avoidable_unresolved=not correct and extra <= budget - spent,
            supported_but_incomplete=visible.decision == "unknown" and goal.decision != "unknown",
        )
