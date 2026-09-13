"""Registered prompt sensitivity probe, preserving the earlier constant outputs."""

from disastertrace.monitoring_fixed_v1.aviation import SYSTEM
from disastertrace.monitoring_fixed_v1.contracts import canonical

EXAMPLE = (
    'Return exactly JSON with two keys: {"probability":0.1,"e_status":"undetermined"}.'
)


def model_messages(bundle, variant):
    if variant == "no_filled_example":
        instruction = (
            "Return exactly one JSON object containing only probability and e_status. "
            "Compute both values from the task and evidence; there are no default values. "
            "probability must be a JSON number; e_status must be one of the permitted strings."
        )
    elif variant == "alternate_filled_example":
        instruction = 'Return exactly JSON with two keys: {"probability":0.7,"e_status":"refuted"}.'
    else:
        raise ValueError("Unregistered prompt variant")
    if SYSTEM.count(EXAMPLE) != 1:
        raise ValueError("Original prompt differs from the audited literal example")
    return [
        {"role": "system", "content": SYSTEM.replace(EXAMPLE, instruction)},
        {"role": "user", "content": canonical(bundle.policy_view())},
    ]
