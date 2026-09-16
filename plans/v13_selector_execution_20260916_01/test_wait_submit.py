"""No network: resource-release and one-create authority regression checks."""

import json

import pytest

import wait_submit as scheduler


def reply(code=0, stdout="", stderr=""):
    return {"returncode": code, "stdout": stdout, "stderr": stderr}


@pytest.mark.parametrize("response,expected", [
    (reply(stdout="job pt-example submitted successfully"), ("accepted", "pt-example")),
    (reply(70, stderr="429 MEMBER_QUOTA_EXCEEDED"), ("quota_rejected", None)),
    (reply(None, stderr="429 MEMBER_QUOTA_EXCEEDED"), ("unknown", None)),
    (reply(1, stderr="transport disconnected"), ("unknown", None)),
    (reply(70, stdout="job pt-example submitted successfully", stderr="429 MEMBER_QUOTA_EXCEEDED"), ("unknown", None)),
    (reply(stdout="unrecognized success"), ("unknown", None)),
])
def test_submission_outcome(response, expected):
    assert scheduler.classify_submission(response) == expected


def test_only_new_verified_release_allows_create():
    states = [{"job_id": "a", "CPU": 8, "state": "RUNNING"}]
    before = scheduler.DEADLINE - 10
    assert not scheduler.may_submit(states, (), False, before)
    states[0]["state"] = "SUCCEEDED"
    assert scheduler.may_submit(states, (), False, before)
    assert not scheduler.may_submit(states, ("a",), False, before)
    assert not scheduler.may_submit(states, (), True, before)
    assert not scheduler.may_submit(states, (), False, scheduler.DEADLINE)
    states[0]["CPU"] = 4
    assert not scheduler.may_submit(states, (), False, before)
    states.append({"job_id": "b", "CPU": 4, "state": "FAILED"})
    assert scheduler.may_submit(states, (), False, before)
    assert scheduler.release_signature(states) == ("a", "b")


def test_failed_query_is_not_empty_job_listing():
    assert scheduler.parse_jobs(reply(stdout="No jobs found\n")) == []
    assert scheduler.parse_jobs(reply(stdout="[]")) == []
    with pytest.raises(ValueError):
        scheduler.parse_jobs(reply(1, stdout="No jobs found"))
    with pytest.raises(ValueError):
        scheduler.parse_jobs(reply(stdout='{"jobs": []}'))


def job_spec():
    argv = ["--aec2-name=pool", "--command=bash /frozen/worker.sh",
            "--container-image-url=image", "--worker-spec=spec"]
    job = {"display_name": scheduler.DISPLAY_NAME, "name": "pt-example",
           "resource_pool": {"name": "pool"}, "roles": [{
               "startup_script": "bash /frozen/worker.sh", "image_path": "image", "total_replicas": 1,
               "resource_spec": [{"name": "spec", "replicas": 1}]}]}
    return job, argv


def test_matching_existing_job_is_adoptable():
    job, argv = job_spec()
    scheduler.validate_job(job, argv)
    assert scheduler.parse_jobs(reply(stdout=json.dumps([job]))) == [job]


@pytest.mark.parametrize("field", ["command", "pool", "replicas"])
def test_mismatched_job_cannot_be_adopted(field):
    job, argv = job_spec()
    if field == "command":
        job["roles"][0]["startup_script"] = "another command"
    elif field == "pool":
        job["resource_pool"]["name"] = "another pool"
    else:
        job["roles"][0]["resource_spec"][0]["replicas"] = 2
    with pytest.raises(ValueError):
        scheduler.validate_job(job, argv)


def test_attempt_directory_consumed_before_dispatch(tmp_path):
    calls = []
    def dispatch(argv):
        calls.append(argv)
        return reply(70, stderr="429 MEMBER_QUOTA_EXCEEDED")
    path = tmp_path / "attempt"
    assert scheduler.submit_once(["create"], path, dispatch)[0] == "quota_rejected"
    assert len(calls) == 1
    with pytest.raises(FileExistsError):
        scheduler.submit_once(["create"], path, dispatch)
    assert len(calls) == 1
    assert json.loads((path / "RESULT.json").read_text())["status"] == "quota_rejected"


def test_interrupted_dispatch_claim_cannot_be_reopened(tmp_path):
    def interrupted(_):
        raise RuntimeError("interrupted")
    path = tmp_path / "attempt"
    with pytest.raises(RuntimeError):
        scheduler.submit_once(["create"], path, interrupted)
    assert (path / "CLAIM.json").exists()
    with pytest.raises(FileExistsError):
        scheduler.submit_once(["create"], path, interrupted)
