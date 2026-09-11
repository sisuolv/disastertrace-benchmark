"""Protocol revision removing the output-wrapper ambiguity observed in wave1."""

from public_inputs import SYSTEM as BASE_SYSTEM, request as base_request

SYSTEM = BASE_SYSTEM + (
    ' Your reply must be the action object itself. A final reply has exactly two top-level keys: '
    '"decision" and "citations". A read reply has exactly one top-level key: "read". '
    'Do not wrap the action in another object. Do not output the question, instructions, remaining budget, '
    'reasoning, or any other fields.'
)


def request(episode, read_ids, representation, mode, budget, final_only=False):
    public, assets = base_request(episode, read_ids, representation, mode, budget, final_only)
    can_read = public.pop("output_contract") is not None
    public.pop("final_contract")
    public.pop("instruction")
    public["reply_format"] = (
        'Reply with exactly {"decision":"yes","citations":["ID"]}, '
        '{"decision":"no","citations":["ID"]}, or '
        '{"decision":"unknown","citations":["ID"]}. Replace ID with acquired card IDs; '
        'use [] if the decision is supported by catalog structure alone. '
        'The citations list may contain several acquired IDs. '
        + ('Alternatively, acquire one unread card by replying exactly {"read":"ID"}. '
           'Choose one action per reply.' if can_read else 'No read action is permitted at this step.')
    )
    return public, assets
