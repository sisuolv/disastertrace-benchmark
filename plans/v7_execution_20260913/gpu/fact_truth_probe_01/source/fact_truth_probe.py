"""Explicit truth vocabulary with paired E-only and E/F joint tasks."""

from disastertrace.monitoring_fixed_v1.contracts import canonical

COMMON = """Answer a factual query about the PAST registered neighbor report slots in E_question. The proposition is existential: AT LEAST ONE registered slot has reported visibility strictly below threshold_m. Use only the assets disclosed in this frozen snapshot. fact_truth is one of four JSON strings: true, false, unknown, conflict. Return true only if a disclosed report's visibility interval proves it is below threshold_m. Return false only if EVERY registered slot is disclosed and its report interval proves it is NOT below threshold_m. Return unknown if the proposition cannot yet be determined, including unqueried or unresolved slots unless another disclosed slot already proves the existential proposition. Return conflict only for inconsistent source facts, not ordinary uncertainty. The presence of some evidence does not itself make the proposition true. Use visibility bounds in meters, including open/closed endpoints; a lower bound already above threshold proves that report is not below. There are no default answers and no example output values. Timestamps are UTC microseconds. The parsed intervals describe native product facts, not error-free physical weather. Do not retrieve external sources or use memorized weather outcomes. Return only JSON, no explanations."""


def model_messages(bundle, variant):
    if variant == "explicit_truth_E_only":
        task = " Your output object must contain exactly the key fact_truth. Do not forecast the future F target in this condition."
    elif variant == "explicit_truth_joint_EF":
        task = (
            " Your output object must contain exactly fact_truth and probability. "
            "probability is your numeric [0,1] forecast for the separate FUTURE native routine visibility report target. "
            "Use the common full TAF and frozen prior-month research probability; you may retain that baseline. "
            "TEMPO is not an official event probability. The past E proposition and future F target are different: "
            "unknown E does not force F probability to 0.5, and known E does not determine the future."
        )
    else:
        raise ValueError("Unregistered fact-truth condition")
    return [
        {"role": "system", "content": COMMON + task},
        {"role": "user", "content": canonical(bundle.policy_view())},
    ]


TRUTH_TO_SUPPORT = {
    "true": "supported",
    "false": "refuted",
    "unknown": "undetermined",
    "conflict": "inconsistent",
}
