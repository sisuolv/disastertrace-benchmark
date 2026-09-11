"""Atomic measurement and one-use collection regressions; no model inference."""

import copy
import json
import os
import time
from collections import Counter
from pathlib import Path

import pytest

from disastertrace.multimodal_atomic_v1.adapter import decode_atomic
from disastertrace.multimodal_atomic_v1.audit import reconstruct, validate_plan
from disastertrace.multimodal_atomic_v1.references import control, reference
from disastertrace.multimodal_atomic_v1.runner import collect
from disastertrace.multimodal_atomic_v1.scoring import parse, parsed, score
from disastertrace.multimodal_atomic_v1.tasks import build
from disastertrace.multimodal_v1.storage import canonical, digest, read, write


@pytest.fixture(scope="module")
def prepared():
    seed = Path(
        os.environ.get(
            "ATOMIC_SEED_BUILD",
            str(
                Path(__file__).resolve().parents[1]
                / "artifacts/multimodal_v1/mm0_2_20260909/build_02"
            ),
        )
    )
    plan = build(seed / "public/requests")
    geometry = {g["artifact_id"]: g for g in read(seed / "private/geometry_lineage.json")}
    refs = {t["task_id"]: reference(t, geometry) for t in plan["tasks"]}
    return plan, refs


def task_of(prepared, tid):
    plan, refs = prepared
    task = next(t for t in plan["tasks"] if t["task_id"] == tid)
    return task, copy.deepcopy(refs[tid])


def test_exact_scope_and_disjoint_balanced_workers(prepared):
    plan, _ = prepared
    validate_plan(plan)
    families = {t["task_id"]: t["family"] for t in plan["tasks"]}
    for ids in plan["assignments"].values():
        counts = Counter(families[tid] for tid in ids)
        assert set(counts) == {"spatial", "watch", "logic", "selection"}
        assert max(counts.values()) - min(counts.values()) <= 1


def test_duplicate_shard_is_rejected(prepared):
    plan = copy.deepcopy(prepared[0])
    plan["assignments"]["1"][0] = plan["assignments"]["0"][0]
    with pytest.raises(ValueError):
        validate_plan(plan)


@pytest.mark.parametrize("family", ["spatial", "watch", "logic", "selection"])
def test_independent_reference_control_and_public_projection(prepared, family):
    plan, refs = prepared
    for task in plan["tasks"]:
        if task["family"] == family:
            assert control(task) == refs[task["task_id"]]
            decoded = decode_atomic(task)
            assert "image_png_base64" not in decoded.public_text
            assert "geometry_lineage" not in decoded.public_text
            assert "carrier" not in task
            assert len(decoded.images) == (
                1 if family == "spatial" and task["inputs"]["evidence"] else 0
            )
            result = score(
                task, refs[task["task_id"]], parsed(json.dumps(control(task)), family), "eos"
            )
            assert result["strict_correct"]


@pytest.mark.parametrize(
    "raw",
    [
        '{"state":[]}',
        '{"state":{"A":{"inspection_required":1}}}',
        '{"state":{"A":{"inspection_required":true,"inspection_required":false}}}',
        '{"state":{"A":{"inspection_required":NaN}}}',
        '```json\n{"state":{}}\n```',
        '{"state":{},"explanation":"x"}',
    ],
)
def test_reject_malformed_structure(raw):
    with pytest.raises(ValueError):
        parse(raw, "logic")


def test_missing_c_is_structural_valid_but_incomplete(prepared):
    task, gold = task_of(prepared, "selection-base-c4")
    answer = copy.deepcopy(gold)
    del answer["state"]["C"]
    result = score(task, gold, parsed(json.dumps(answer), "selection"), "eos")
    assert result["structural_valid"] and not result["query_complete"]
    assert result["missing_sites"] == ["C"] and not result["strict_correct"]
    assert result["citation_fields"]["denominator"] == 6


def test_extra_site_fails_coverage(prepared):
    task, gold = task_of(prepared, "watch-watch-01-A")
    answer = copy.deepcopy(gold)
    answer["state"]["C"] = answer["state"]["A"]
    result = score(task, gold, parsed(json.dumps(answer), "watch"), "eos")
    assert result["structural_valid"] and result["extra_sites"] == ["C"]
    assert not result["strict_correct"]


def test_wrong_existing_line_legal_but_incorrect(prepared):
    task, gold = task_of(prepared, "watch-watch-01-A")
    answer = copy.deepcopy(gold)
    answer["state"]["A"]["rule_locator"] = "L1"
    result = score(task, gold, parsed(json.dumps(answer), "watch"), "eos")
    assert result["citation_legal_sites"]["numerator"] == 1
    assert not result["strict_correct"]


@pytest.mark.parametrize("locator", ["2", "L0", "L99", "L02"])
def test_invalid_watch_locators(prepared, locator):
    task, gold = task_of(prepared, "watch-watch-01-A")
    answer = copy.deepcopy(gold)
    answer["state"]["A"]["rule_locator"] = locator
    result = score(task, gold, parsed(json.dumps(answer), "watch"), "eos")
    assert result["citation_legal_sites"]["numerator"] == 0


def test_intensity_is_not_watch_evidence(prepared):
    task, gold = task_of(prepared, "watch-absent-A")
    answer = {"state": {"A": {"watched": True, "rule_source": "context-05", "rule_locator": "L2"}}}
    result = score(task, gold, parsed(json.dumps(answer), "watch"), "eos")
    assert result["citation_legal_sites"]["numerator"] == 0
    assert result["value_fields"]["numerator"] == 0


def test_missing_watch_site_is_null_even_with_list(prepared):
    _, gold = task_of(prepared, "watch-watch-01-C")
    assert gold["state"]["C"] == {"watched": None, "rule_source": None, "rule_locator": None}


def test_stale_map_legal_but_not_current(prepared):
    task, gold = task_of(prepared, "selection-base-c3")
    answer = copy.deepcopy(gold)
    answer["state"]["A"]["map_source"] = "map-01"
    result = score(task, gold, parsed(json.dumps(answer), "selection"), "eos")
    assert result["citation_legal_sites"]["numerator"] == 2
    assert not result["strict_correct"]


def test_pre_c4_queries_do_not_reveal_c(prepared):
    for task in prepared[0]["tasks"]:
        if task["family"] == "selection" and task["inputs"]["source_checkpoint"] != "c4":
            assert [q["site_id"] for q in task["inputs"]["queries"]] == ["A", "B"]


@pytest.mark.parametrize("relation", ["unknown", "boundary_ambiguous", "inside", "outside"])
def test_false_dominates_null(prepared, relation):
    _, gold = task_of(prepared, f"logic-{relation}-false")
    assert gold["state"]["A"]["inspection_required"] is False


def test_non_eos_cannot_be_strict_success(prepared):
    task, gold = task_of(prepared, "logic-inside-true")
    result = score(task, gold, parsed(json.dumps(gold), "logic"), "length")
    assert result["fields_correct"] and not result["strict_correct"]


def test_point_locator_equivalence_and_whole_image_rejection(prepared):
    task, gold = task_of(prepared, "spatial-map-01-A")
    for locator, expected in [("point:A", True), ("whole_image", False)]:
        answer = copy.deepcopy(gold)
        answer["state"]["A"]["map_locator"] = locator
        assert (
            score(task, gold, parsed(json.dumps(answer), "spatial"), "eos")["strict_correct"]
            is expected
        )


def test_no_private_input_injection(prepared):
    task = copy.deepcopy(prepared[0]["tasks"][0])
    task["inputs"]["gold"] = {}
    with pytest.raises(ValueError):
        decode_atomic(task)


class FakeBackend:
    def __init__(self, mode):
        self.settings = {"max_generation_seconds": 1}
        self.mode, self.calls = mode, 0

    def prepare(self, task, slot):
        if self.mode == "preflight_failure":
            raise ValueError("fixture preflight failure")
        write(slot / "processor.json", {"fixture": True})
        return task

    def generate(self, task):
        self.calls += 1
        if self.mode == "unknown":
            raise RuntimeError("fixture dispatch interruption")
        return '{"state":[]}', {"fixture": True}


@pytest.mark.parametrize(
    "mode,status,calls",
    [
        ("invalid", "received_invalid", 1),
        ("unknown", "unknown", 1),
        ("preflight_failure", "failed_preflight", 0),
    ],
)
def test_collection_keeps_failure_and_refuses_relaunch(tmp_path, prepared, mode, status, calls):
    task, _ = task_of(prepared, "logic-inside-true")
    backend = FakeBackend(mode)
    result = collect(tmp_path / "live", [task], backend, "fixture", time.time() + 60)
    assert result["counts"] == {status: 1} and backend.calls == calls
    if mode == "invalid":
        assert (tmp_path / "live" / task["task_id"] / "raw.txt").read_text() == '{"state":[]}'
    with pytest.raises(FileExistsError):
        collect(tmp_path / "live", [task], backend, "fixture", time.time() + 60)
    assert backend.calls == calls


def test_expired_window_has_no_dispatch(tmp_path, prepared):
    backend = FakeBackend("invalid")
    result = collect(
        tmp_path / "live", prepared[0]["tasks"][:1], backend, "fixture", time.time() - 1
    )
    assert result["counts"] == {"unattempted": 1} and backend.calls == 0
    assert not list(tmp_path.rglob("intent.json"))


@pytest.fixture
def capture_fixture(tmp_path, prepared):
    plan, refs = prepared
    write(tmp_path / "REQUEST_PLAN.json", plan)
    write(tmp_path / "references.json", refs)
    execution = {
        "settings": {"max_new_tokens": 2048},
        "max_generations": 40,
        "not_after_unix": time.time() + 3600,
        "bound_files": {
            name: digest((tmp_path / name).read_bytes())
            for name in ["REQUEST_PLAN.json", "references.json"]
        },
    }
    write(tmp_path / "EXECUTION.json", execution)
    identity = digest((tmp_path / "EXECUTION.json").read_bytes())

    class ControlBackend:
        def __init__(self):
            self.settings = {"max_generation_seconds": 1}

        def prepare(self, task, slot):
            write(
                slot / "processor.json",
                {"request_sha256": digest(canonical(task).encode()), "fixture": True},
            )
            return task

        def generate(self, task):
            return canonical(control(task)), {
                "output_ids": [0],
                "output_tokens": 1,
                "finish_reason": "eos",
                "seconds": 1.0,
            }

    by_id = {t["task_id"]: t for t in plan["tasks"]}
    for worker, ids in plan["assignments"].items():
        collect(
            tmp_path / "gpu_runs" / worker / "live",
            [by_id[tid] for tid in ids],
            ControlBackend(),
            identity,
            execution["not_after_unix"],
        )
    return tmp_path


def test_raw_report_reconstruction(capture_fixture):
    report = reconstruct(capture_fixture)
    assert report["dispatches"] == report["planned"] == 40
    assert report["revision_diagnostic_gate"]


@pytest.mark.parametrize("changed", ["request.json", "processor.json", "outcome.json"])
def test_auditor_rejects_capture_tampering(capture_fixture, changed):
    slot = capture_fixture / "gpu_runs/0/live/spatial-map-01-A"
    data = read(slot / changed)
    if changed == "request.json":
        data["inputs"]["queries"] = []
    elif changed == "processor.json":
        data["fixture"] = False
    else:
        data["value"]["state"]["A"]["relation"] = "inside"
    (slot / changed).write_text(json.dumps(data))
    with pytest.raises(ValueError):
        reconstruct(capture_fixture)


def test_missing_worker_retains_full_denominator(capture_fixture):
    (capture_fixture / "gpu_runs/3").rename(capture_fixture / "fixture-hidden-worker")
    report = reconstruct(capture_fixture)
    assert report["planned"] == 40 and report["dispatches"] == 30
    assert report["status_counts"]["unattempted"] == 10
    assert not report["revision_diagnostic_gate"]
