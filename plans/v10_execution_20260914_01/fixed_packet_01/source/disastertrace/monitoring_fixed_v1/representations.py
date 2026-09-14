"""Task-focused views of the same disclosed native records, without E answers."""

from .contracts import canonical
from .heads import SYSTEMS, _aviation_target, _check_head
from .heads import model_messages as full_messages

VERSION = "native_task_focus.v1"


def focused_view(bundle, head):
    _check_head(head)
    _aviation_target(bundle)
    row = bundle.policy_view()
    question = row["baseline"]["content"]["E_question"]
    assets = row["assets"]
    slots = []
    for qid in question["query_ids"]:
        disclosed = [a for a in assets if a["content"]["query_id"] == qid]
        slots.append(
            {
                "query_id": qid,
                "disclosure": "acquired" if disclosed else "not_acquired",
                "native_sources": [
                    {
                        k: a[k]
                        for k in (
                            "asset_id",
                            "raw",
                            "content",
                            "available_at",
                            "completed_at",
                            "source_revision",
                            "reference_kind",
                            "support_assumption",
                            "support_rule_version",
                            "receipt_ids",
                        )
                    }
                    for a in disclosed
                ],
            }
        )
    view = {
        "representation": VERSION,
        "opportunity_id": row["opportunity_id"],
        "cutoff": row["cutoff"],
        "E_question": question,
        "registered_native_slots": slots,
        "availability_basis": row["availability_basis"],
    }
    if head != "e_only":
        view.update(target=row["target"], baseline=row["baseline"], state=row["state"])
    return view


def model_messages(bundle, head, representation="full_bundle"):
    if representation == "full_bundle":
        return full_messages(bundle, head)
    if representation != VERSION:
        raise ValueError("Unregistered input representation")
    return [
        {
            "role": "system",
            "content": SYSTEMS[head]
            + (
                " Registered native slots are listed individually in registered_native_slots. "
                "Each acquired slot contains its unchanged native report content and intervals. "
                "A not_acquired slot is unqueried, not a source claim of good weather. "
                "These rows do not supply an answer to the E proposition."
            ),
        },
        {"role": "user", "content": canonical(focused_view(bundle, head))},
    ]
