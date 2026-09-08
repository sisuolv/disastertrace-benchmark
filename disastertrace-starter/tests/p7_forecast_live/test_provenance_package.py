"""Real native package closure and ACP evidence rejection before model scoring."""

from copy import deepcopy
from pathlib import Path

import pytest

from disastertrace.forecast_live import acp, package, provenance
from disastertrace.forecast_task.common import fingerprint, read


def job_fixture():
    request = {"display_name": "dt-p7-test", "command": "bound-command"}
    job = {
        "name": "pt-test",
        "display_name": request["display_name"],
        "state": "SUCCEEDED",
        "resource_pool": {"name": acp.CLUSTER},
        "fault_tolerance": {"backoff_limit": 0},
        "lme": {"current_retries": 0},
        "roles": [
            {
                "startup_script": request["command"],
                "image_path": acp.IMAGE,
                "total_replicas": 1,
                "resource_spec": [
                    {
                        "name": acp.SPEC,
                        "replicas": 1,
                        "limits": {"nvidia.com/gpu": "1"},
                        "requests": {"nvidia.com/gpu": "1"},
                    }
                ],
            }
        ],
        "mount": [{"mount_path": "/mnt/afs", "id": "01a04263-91e5-7603-bc01-c67e503da6b5"}],
    }
    return request, job


@pytest.mark.parametrize(
    "mutation",
    [
        "name",
        "cluster",
        "retry",
        "recovered_retry",
        "command",
        "image",
        "gpu",
        "replicas",
        "volume",
    ],
)
def test_actual_platform_job_mismatch_is_rejected(mutation):
    request, job = job_fixture()
    assert provenance.job_record(job, request)["released"]
    if mutation == "name":
        job["display_name"] = "historical-job"
    elif mutation == "cluster":
        job["resource_pool"]["name"] = "other-cluster"
    elif mutation == "retry":
        job["fault_tolerance"]["backoff_limit"] = 1
    elif mutation == "recovered_retry":
        job["lme"]["current_retries"] = 1
    elif mutation == "command":
        job["roles"][0]["startup_script"] = "unbound-command"
    elif mutation == "image":
        job["roles"][0]["image_path"] = "different-image"
    elif mutation == "gpu":
        job["roles"][0]["resource_spec"][0]["limits"]["nvidia.com/gpu"] = "4"
    elif mutation == "replicas":
        job["roles"][0]["total_replicas"] = 2
    else:
        job["mount"][0]["id"] = "different-volume"
    with pytest.raises(ValueError):
        provenance.job_record(job, request)


def test_missing_worker_evidence_retains_worker_but_cannot_authenticate_model_answers():
    plan = {"execution_id": "e", "phase_id": "p", "source_files": {}}
    phase = {"execution_id": "e", "source_files": {}, "kind": "model", "workers": 4}
    proof = {**plan, "phase_claim": phase, "workers": [{"worker_id": i} for i in range(4)]}
    audits = [{"attempted": 0, "raw_returned": 0, "claim_present": False} for i in range(4)]
    records = provenance.validate_phase(proof, plan, audits, [])
    assert len(records) == 4 and all(r["state"] == "unsubmitted" for r in records)
    audits[0]["attempted"] = 1
    with pytest.raises(ValueError, match="without a submission"):
        provenance.validate_phase(proof, plan, audits, [])


def test_same_terminal_job_cannot_be_assigned_to_two_workers():
    plan = {"execution_id": "e", "phase_id": "p", "source_files": {}}
    phase = {"execution_id": "e", "source_files": {}, "kind": "model", "workers": 4}
    proof = {**plan, "phase_claim": phase, "workers": []}
    audits = []
    for i in range(4):
        request, job = job_fixture()
        request.update(
            plan,
            worker_id=i,
            kind="model",
            phase_claim_sha256=fingerprint(phase),
            max_model_attempts=0,
        )
        proof["workers"].append({"worker_id": i, "request": request, "job_details": job})
        audits.append(
            {"attempted": 0, "raw_returned": 0, "claim_present": False, "status": "absent_manifest"}
        )
    with pytest.raises(ValueError, match="same ACP job"):
        provenance.validate_phase(proof, plan, audits, [])


def test_real_native_freeze_closure_and_disjoint_preview_counts(tmp_path):
    project = Path(__file__).resolve().parents[2]
    root = tmp_path / "execution"
    plan = package.freeze(
        project / "artifacts/p7_forecast_task_v1/execution_v1",
        project / "artifacts/p6_live_v1/execution_live_02",
        root,
    )
    checked, _, slots = package.verify(root, code=True)
    assert checked == plan and plan["generation_authorized"] is False
    assert [sum(s["worker_id"] == i for s in slots) for i in range(4)] == [390, 390, 384, 378]
    assert len({s["attempt_id"] for s in slots}) == 1542
    public = read(root / "task/data/public.json")
    source = read(root / "task/schedule.json")
    changed = package.assign(public, source, "different-phase")
    assert not {s["attempt_id"] for s in changed} & {s["attempt_id"] for s in slots}
    path = root / "source/disastertrace/forecast_live/adapter.py"
    path.write_text(path.read_text() + "\n# changed fixture\n")
    with pytest.raises(ValueError, match="inventory"):
        package.verify(root, code=True)


def test_preflight_requires_terminal_release_and_identical_implementation():
    from disastertrace.forecast_live import adapter, launch
    from disastertrace.forecast_live.backend import DECODER

    actual_engine = {
        k: adapter.SETTINGS[k]
        for k in (
            "max_model_len",
            "tensor_parallel_size",
            "enable_prefix_caching",
            "max_num_seqs",
            "max_num_batched_tokens",
            "enforce_eager",
            "seed",
        )
    }
    actual_engine["dtype"] = "torch.bfloat16"
    plan = {
        "kind": "preflight",
        "generation_authorized": False,
        "execution_id": "e",
        "source_files": {},
        "settings": adapter.SETTINGS,
        "task_package_id": "t",
        "backend_files": {},
        "model_identity": "m",
        "environment_sha256": "env",
    }
    request = {
        "kind": "preflight",
        "execution_id": "e",
        "source_files": {},
        "source_cci_hostname": "cpu-host",
        "display_name": "test-preflight",
    }
    obs = {
        "visible_gpu_count": 1,
        "device_name": "NVIDIA H100 80GB HBM3",
        "capability": [9, 0],
        "total_memory_bytes": 80_000_000_000,
        "structured_decoding": DECODER,
        "actual_engine": actual_engine,
        "settings": adapter.SETTINGS,
        "vllm_use_v1": "1",
        "v1_multiprocessing": "0",
        "request_identity": "attempt_id_direct_engine_add_request",
        "backend_files": {},
        "model_identity": "m",
        "environment_sha256": "env",
    }
    result = {
        "status": "passed",
        "generate_disabled": True,
        "model_calls": 0,
        "request_sha256": fingerprint(request),
        "hostname": "gpu-host",
        "runtime_observation": obs,
    }
    job = {
        "state": "SUCCEEDED",
        "cluster": acp.CLUSTER,
        "gpu_count": 1,
        "released": True,
        "job_id": "pt-test",
        "display_name": "test-preflight",
    }
    proof = {
        "request": request,
        "result": result,
        "job": job,
        "execution": plan,
        "validation": {"status": "passed"},
    }
    launch.validate_preflight(proof, plan)
    changed = deepcopy(proof)
    changed["job"]["released"] = False
    with pytest.raises(ValueError):
        launch.validate_preflight(changed, plan)
    with pytest.raises(ValueError, match="implementation"):
        launch.validate_preflight(proof, {**plan, "source_files": {"changed": "bytes"}})
