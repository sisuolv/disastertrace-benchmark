"""Public checkpoint view used by controlled agents.

This boundary removes scorer labels and any evidence that was not available at
the fixed decision cutoff before the payload is serialized for a provider.
``public_checkpoint`` returns one checkpoint's single current snapshot;
``public_prefix`` returns the ordered history visible at the same cutoff.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def _is_timestamp(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


_VISIBLE_AVAILABILITY = {"available", "known"}


def _is_visible_availability(value: Any) -> bool:
    # A bare ``value in {"available", "known"}`` raises TypeError for any
    # unhashable value (e.g. a list) instead of just being false. Availability
    # is only ever meaningful as one of these two strings; anything else,
    # hashable or not, is simply not a visible label -- fail closed silently,
    # the same way every other malformed-input path in this module already
    # does, not with a crash.
    return isinstance(value, str) and value in _VISIBLE_AVAILABILITY


def public_checkpoint(episode: Mapping[str, Any], checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(episode, Mapping) or not isinstance(checkpoint, Mapping):
        raise ValueError("episode and checkpoint mappings are required")
    target_start, target_end = episode.get("target_start"), episode.get("target_end")
    cutoff = checkpoint.get("witness", {}).get("as_of") if isinstance(checkpoint.get("witness"), Mapping) else None
    if cutoff is None:
        cutoff = episode.get("as_of")
    if not isinstance(target_start, int) or not isinstance(target_end, int) or target_start >= target_end:
        raise ValueError("Future target interval is required")
    if not isinstance(cutoff, int) or cutoff >= target_start:
        raise ValueError("Public decision cutoff must precede target start")
    evidence: dict[str, Any] = {}
    if _is_visible_availability(checkpoint.get("availability")):
        witness = checkpoint.get("witness")
        candidate = witness.get("current_projection") if isinstance(witness, Mapping) else None
        available_at = witness.get("available_at") if isinstance(witness, Mapping) else None
        # A "known" label only means the qualifier recorded an available_at
        # without judging it against any cutoff (see evidence_qualification_v18
        # ._availability: "known" is returned exactly when as_of was None at
        # qualification time). It is therefore not, by itself, proof the
        # record was legitimately visible at *this* checkpoint's cutoff; an
        # undisclosed future arrival time must never reach a Raw payload.
        if _is_timestamp(available_at) and available_at <= cutoff and isinstance(candidate, Mapping):
            evidence = deepcopy(dict(candidate))
    return {
        "station": episode.get("station"),
        "target_start": target_start,
        "target_end": target_end,
        "cutoff": cutoff,
        "current_evidence": evidence,
    }


def public_prefix(episode: Mapping[str, Any], checkpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the full legitimate evidence prefix at ``checkpoint``'s cutoff.

    Entries keep the order of ``episode["qualifications"]`` (the arrival
    stream).  An entry is kept only when all of these hold:

    * its ``availability`` is ``available`` or ``known`` (the labels
      ``public_checkpoint`` accepts);
    * its own cutoff (``witness["as_of"]``, else ``episode["as_of"]``) is not
      after the checkpoint cutoff;
    * its ``witness["available_at"]`` is an integer that is not after the
      checkpoint cutoff.  ``known`` labels were never compared with any
      cutoff, so this check is what keeps them from leaking a later arrival.

    Availability labels are relative to each entry's own ``as_of``, so an
    entry labelled ``not_yet_available`` stays excluded even when a later
    checkpoint cutoff would admit it.

    Each kept entry holds only ``issued_at``, ``available_at``,
    ``current_relevance`` and ``current_projection``, deep-copied.  Scorer
    labels such as ``status`` or ``target_content_change`` never cross this
    boundary, and the result shares no mutable state with the episode.

    ``scripts/build_v18_dev_episodes.py`` qualifies all rows of an episode
    against one shared ``as_of``.  With that data model, every checkpoint of
    an episode gets the same prefix.
    """
    # Delegate validation and cutoff resolution to public_checkpoint so both
    # views accept and reject exactly the same checkpoints.
    cutoff = public_checkpoint(episode, checkpoint)["cutoff"]
    qualifications = episode.get("qualifications", ())
    if not isinstance(qualifications, (list, tuple)):
        raise ValueError("episode qualifications must be a list of qualification mappings")
    prefix: list[dict[str, Any]] = []
    for entry in qualifications:
        if not isinstance(entry, Mapping) or not _is_visible_availability(entry.get("availability")):
            continue
        witness = entry.get("witness")
        if not isinstance(witness, Mapping):
            continue
        entry_cutoff = witness.get("as_of")
        if entry_cutoff is None:
            entry_cutoff = episode.get("as_of")
        if not _is_timestamp(entry_cutoff) or entry_cutoff > cutoff:
            continue
        available_at = witness.get("available_at")
        if not _is_timestamp(available_at) or available_at > cutoff:
            continue
        projection = witness.get("current_projection")
        prefix.append(
            {
                "issued_at": deepcopy(witness.get("issued_at")),
                "available_at": available_at,
                "current_relevance": deepcopy(witness.get("current_relevance")),
                "current_projection": deepcopy(dict(projection)) if isinstance(projection, Mapping) else {},
            }
        )
    return prefix
