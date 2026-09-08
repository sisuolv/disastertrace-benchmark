"""Strict, offline DisasterBench inherited-label adapter and scorer.

Comparison follows the canonical-field semantics of DisasterBench_Open's
evaluators/evaluators.py (ordered plans/outputs, unordered dependence lists).
Unlike the upstream completion parser, this contract does not repair outputs,
accept aliases, or admit empty plans. Agreement is not actual tool execution.

Upstream license notice (https://github.com/TamuChen18/DisasterBench_Open):

MIT License
Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import hashlib
import json
import re
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "disastertrace.disasterbench.v1"
SCORER_VERSION = "disasterbench_inherited_strict_v1"
LABEL_ORIGIN = "inherited_upstream_unreviewed"
_STEP_KEYS = {"step", "agent", "inputs", "outputs", "dependence", "dependence_content"}
_GENERATED = re.compile(r"<GENERATED>-(\d+)(?:-<([^>]+)>)?")
_STRING_LIST = {
    "type": "array",
    "items": {"type": "string", "minLength": 1},
    "minItems": 1,
    "uniqueItems": True,
}
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["task_id", "structured_plan"],
    "properties": {
        "task_id": {"type": "string", "minLength": 1},
        "structured_plan": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": sorted(_STEP_KEYS),
                "properties": {
                    "step": {"type": "integer", "minimum": 0},
                    "agent": {"type": "string", "minLength": 1},
                    "inputs": {"type": "object", "additionalProperties": {"type": "string"}},
                    "outputs": _STRING_LIST,
                    "dependence": {
                        "type": "array",
                        "minItems": 1,
                        "uniqueItems": True,
                        "items": {"type": "integer", "minimum": -1},
                    },
                    "dependence_content": {
                        "anyOf": [
                            {"type": "null"},
                            {"type": "object", "additionalProperties": _STRING_LIST},
                        ],
                    },
                },
            },
        },
    },
}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non_json_constant:{value}")


def _load_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def _string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(x, str) and bool(x.strip()) for x in value)
        and len(set(value)) == len(value)
    )


def _plan_issues(plan: Any, tools: dict | None = None) -> list[str]:
    if not isinstance(plan, list) or not plan:
        return ["plan_must_be_nonempty_array"]
    issues = []
    for index, step in enumerate(plan):
        prefix = f"step[{index}]"
        if not isinstance(step, dict) or set(step) != _STEP_KEYS:
            issues.append(f"{prefix}:canonical_fields_required")
            continue
        if type(step["step"]) is not int or step["step"] != index:
            issues.append(f"{prefix}:step_id_must_equal_array_index")
        agent, inputs, outputs = step["agent"], step["inputs"], step["outputs"]
        if not isinstance(agent, str) or not agent.strip():
            issues.append(f"{prefix}:agent_must_be_nonempty_string")
        if not isinstance(inputs, dict) or not all(
            isinstance(k, str) and bool(k) and isinstance(v, str) for k, v in inputs.items()
        ):
            issues.append(f"{prefix}:inputs_must_be_string_map")
        if not _string_list(outputs):
            issues.append(f"{prefix}:outputs_must_be_unique_nonempty_string_list")
        dependencies, content = step["dependence"], step["dependence_content"]
        valid_dependencies = (
            isinstance(dependencies, list)
            and bool(dependencies)
            and all(type(d) is int for d in dependencies)
            and len(set(dependencies)) == len(dependencies)
            and (dependencies == [-1] or all(0 <= d < index for d in dependencies))
        )
        if not valid_dependencies:
            issues.append(f"{prefix}:dependence_must_reference_prior_steps_or_minus_one")
        elif dependencies == [-1]:
            if content is not None:
                issues.append(f"{prefix}:independent_step_content_must_be_null")
        elif (
            not isinstance(content, dict)
            or set(content) != {str(d) for d in dependencies}
            or not all(_string_list(v) for v in content.values())
        ):
            issues.append(f"{prefix}:dependence_content_must_match_dependency_ids")
        else:
            for dep, names in content.items():
                producer = plan[int(dep)]
                if (
                    not isinstance(producer, dict)
                    or not _string_list(producer.get("outputs"))
                    or not set(names).issubset(producer["outputs"])
                ):
                    issues.append(f"{prefix}:dependency_output_not_produced:{dep}")
        if isinstance(inputs, dict) and valid_dependencies:
            for name, value in inputs.items():
                if not isinstance(value, str) or "<GENERATED>" not in value:
                    continue
                match = _GENERATED.fullmatch(value)
                if not match or int(match[1]) not in dependencies:
                    issues.append(f"{prefix}:generated_input_missing_dependency:{name}")
                elif match[2] is not None:
                    producer = plan[int(match[1])]
                    if (
                        not isinstance(producer, dict)
                        or not _string_list(producer.get("outputs"))
                        or match[2] not in producer["outputs"]
                    ):
                        issues.append(f"{prefix}:generated_input_output_not_produced:{name}")
        if tools is not None:
            if not isinstance(agent, str) or agent not in tools:
                issues.append(f"{prefix}:unknown_tool")
            else:
                if not isinstance(inputs, dict) or set(inputs) != set(tools[agent]["input"]):
                    issues.append(f"{prefix}:manifest_input_keys_mismatch")
                if not _string_list(outputs) or set(outputs) != set(tools[agent]["output"]):
                    issues.append(f"{prefix}:manifest_output_keys_mismatch")
    return issues


def _source_id(row: Any) -> str | None:
    if not isinstance(row, dict):
        return None
    value = row.get("task_id")
    if type(value) not in (str, int) or (isinstance(value, str) and not value.strip()):
        return None
    return f"disasterbench:{value}"


def build_disasterbench(data_path: Path, tools_path: Path) -> dict:
    """Admit structurally consistent upstream labels; never repair a source label.

    All tools are supplied to every task so tool selection does not leak labels.
    Data failures are quarantined per source line; an invalid manifest is fatal.
    This is a broad-disaster comparison set, not an extreme-weather-only filter.
    """
    data_bytes, tools_bytes = data_path.read_bytes(), tools_path.read_bytes()
    tools = _load_json(tools_bytes.decode("utf-8-sig"))
    if not isinstance(tools, dict) or not tools:
        raise ValueError("tool manifest must be a nonempty object")
    for name, tool in tools.items():
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(tool, dict)
            or set(tool) != {"desc", "input", "output"}
            or not isinstance(tool["desc"], str)
            or not all(
                isinstance(tool[k], dict)
                and all(isinstance(a, str) and isinstance(b, str) for a, b in tool[k].items())
                for k in ("input", "output")
            )
        ):
            raise ValueError(f"invalid tool manifest entry: {name}")
    rows, quarantine = [], []
    for line_number, line in enumerate(data_bytes.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append((line_number, _load_json(line)))
        except ValueError as exc:
            quarantine.append(
                {"source_line": line_number, "task_id": None, "issues": [f"invalid_json:{exc}"]}
            )
    id_counts = Counter(_source_id(row) for _, row in rows)
    public, references = [], []
    hashes = {
        "data_sha256": hashlib.sha256(data_bytes).hexdigest(),
        "tools_sha256": hashlib.sha256(tools_bytes).hexdigest(),
    }
    for line_number, row in rows:
        task_id = _source_id(row)
        issues = []
        if not isinstance(row, dict) or set(row) != {
            "task_id",
            "task_desc",
            "structured_plan",
            "source",
        }:
            issues.append("source_row_schema_mismatch")
        if task_id is None:
            issues.append("invalid_task_id")
        elif id_counts[task_id] != 1:
            issues.append("duplicate_task_id")
        if isinstance(row, dict):
            if not isinstance(row.get("task_desc"), str) or not row["task_desc"].strip():
                issues.append("task_text_must_be_nonempty_string")
            if not isinstance(row.get("source"), str):
                issues.append("source_must_be_string")
            issues.extend(_plan_issues(row.get("structured_plan"), tools))
        if issues:
            quarantine.append({"source_line": line_number, "task_id": task_id, "issues": issues})
            continue
        source = {
            "dataset": "DisasterBench_Open",
            "original_task_id": row["task_id"],
            "source_line": line_number,
            **hashes,
        }
        public.append(
            {
                "task_id": task_id,
                "task": row["task_desc"],
                "tools": deepcopy(tools),
                "response_schema": deepcopy(RESPONSE_SCHEMA),
                "source": source,
                "instructions": (
                    "Return one JSON object with task_id and a nonempty structured_plan. "
                    "Steps are numbered consecutively from 0 in execution order. Use the canonical "
                    "step fields in response_schema. dependence lists prior step IDs, or [-1] "
                    "with null dependence_content for independent steps. For dependencies, "
                    "dependence_content maps step IDs to required output names. Inputs use "
                    "literal supplied paths or <GENERATED>-N-<output_name> references; "
                    "outputs list tool output names. Plan offline; do not execute tools."
                ),
            }
        )
        references.append(
            {
                "task_id": task_id,
                "structured_plan": deepcopy(row["structured_plan"]),
                "label_origin": LABEL_ORIGIN,
                "source": deepcopy(source),
            }
        )
    quarantine.sort(key=lambda item: item["source_line"])
    counts = Counter(
        issue.split(":", 1)[-1] if issue.startswith("step[") else issue.split(":", 1)[0]
        for item in quarantine
        for issue in item["issues"]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "public_tasks": public,
        "private_references": references,
        "profile": {
            "source_tasks": len(rows)
            + sum(
                item["task_id"] is None
                and any(issue.startswith("invalid_json:") for issue in item["issues"])
                for item in quarantine
            ),
            "admitted_tasks": len(public),
            "quarantined_tasks": len(quarantine),
            "tool_count": len(tools),
            "quarantine": quarantine,
            "schema_issues": dict(sorted(counts.items())),
            "source_hashes": hashes,
            "label_origin": LABEL_ORIGIN,
            "scorer_version": SCORER_VERSION,
            "scope": "broad_disaster_inherited_label_comparison",
            "admission_policy": "strict_canonical_plan_and_manifest_and_dependency_binding_v1",
            "limitations": [
                "No new human review or semantic verification of task-label alignment.",
                "Label agreement does not establish tool executability or disaster-response quality.",
                "Quarantined records are not repaired or included in the scoring denominator.",
            ],
        },
    }


def _equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _index(items: list, kind: str) -> dict:
    if not isinstance(items, list):
        raise ValueError(f"{kind} must be a list")
    result = {}
    for item in items:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("task_id"), str)
            or not item["task_id"]
        ):
            raise ValueError(f"{kind} item requires a nonempty string task_id")
        if item["task_id"] in result:
            raise ValueError(f"duplicate {kind} task_id: {item['task_id']}")
        result[item["task_id"]] = item
    return result


def score_disasterbench(public_tasks: list, private_references: list, predictions: list) -> dict:
    """Score a submission with every admitted expected task in the denominator.

    Unknown/duplicate/unidentifiable submission IDs fail the submission contract.
    A missing answer or invalid plan receives zero for every metric. The strict
    schema is a versioned derived protocol, not the upstream permissive parser.
    """
    tasks, references = (
        _index(public_tasks, "public_tasks"),
        _index(private_references, "references"),
    )
    if not tasks or tasks.keys() != references.keys():
        raise ValueError("nonempty public task and reference ID sets must match exactly")
    submitted = _index(predictions, "predictions")
    if submitted.keys() - tasks.keys():
        raise ValueError(f"unknown prediction task_ids: {sorted(submitted.keys() - tasks.keys())}")
    for task_id, reference in references.items():
        issues = _plan_issues(reference.get("structured_plan"))
        if issues:
            raise ValueError(f"invalid private reference {task_id}: {issues}")
    per_task = []
    fields = {
        "tool_match": ("step", "agent"),
        "parameter_match": ("step", "agent", "inputs", "outputs"),
        "dependency_match": ("step", "agent", "dependence", "dependence_content"),
    }
    for task_id in tasks:
        item = {
            "task_id": task_id,
            "status": "missing",
            "exact_match": 0,
            **{metric: 0 for metric in fields},
            "errors": [],
        }
        prediction = submitted.get(task_id)
        if prediction is not None:
            issues = _plan_issues(prediction.get("structured_plan"))
            if set(prediction) != {"task_id", "structured_plan"}:
                issues.append("prediction_requires_only_task_id_and_structured_plan")
            if issues:
                item.update(status="invalid", errors=issues)
            else:
                expected, actual = (
                    references[task_id]["structured_plan"],
                    prediction["structured_plan"],
                )
                for metric, keys in fields.items():
                    item[metric] = int(
                        len(expected) == len(actual)
                        and all(
                            all(
                                _equal(sorted(a[key]), sorted(b[key]))
                                if key == "dependence"
                                else _equal(a[key], b[key])
                                for key in keys
                            )
                            for a, b in zip(expected, actual)
                        )
                    )
                item["exact_match"] = int(all(item[metric] for metric in fields))
                item["status"] = "correct" if item["exact_match"] else "incorrect"
                item["errors"] = [metric for metric in fields if not item[metric]]
        per_task.append(item)
    count = len(per_task)
    return {
        "schema_version": SCHEMA_VERSION,
        "scorer_version": SCORER_VERSION,
        "interpretation": "inherited_label_agreement_not_tool_execution",
        "aggregate": {
            "expected_tasks": count,
            "submitted_predictions": len(submitted),
            "missing_predictions": sum(x["status"] == "missing" for x in per_task),
            "invalid_predictions": sum(x["status"] == "invalid" for x in per_task),
            "correct_tasks": sum(x["exact_match"] for x in per_task),
            "exact_match_accuracy": sum(x["exact_match"] for x in per_task) / count,
            **{f"{metric}_accuracy": sum(x[metric] for x in per_task) / count for metric in fields},
        },
        "per_task": per_task,
    }
