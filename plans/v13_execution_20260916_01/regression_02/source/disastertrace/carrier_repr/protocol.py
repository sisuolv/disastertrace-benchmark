"""A fork receives its saved source prefix once; branch outputs never become later input."""

from copy import deepcopy


def request(public, slot, history):
    if history:
        raise ValueError("one-step representation branches cannot carry their own outputs")
    bound = public["representation_requests"][slot["slot_id"]]
    if not slot["eligible"] or not bound["eligible"] or bound["messages"] is None:
        raise ValueError("source prefix unavailable; no generation or synthetic replacement")
    if (
        slot["method"] != bound["representation"]
        or slot["source_slot_id"] != bound["source_slot_id"]
    ):
        raise ValueError("representation/source-slot binding differs")
    return deepcopy(bound["messages"])
