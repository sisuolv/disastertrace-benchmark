"""Durable request/response transport for a separately frozen local inference worker."""

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from .execution import PendingExecution
from .targets import canonical_hash


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def publish(path, payload):
    """A partial write cannot become a visible final request or replace a receipt."""
    temporary = path.with_name(path.name + ".writing-" + uuid.uuid4().hex)
    with temporary.open("x") as handle:
        json.dump(payload, handle, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.link(temporary, path)
    temporary.unlink()
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class SpoolBackend:
    """Only resolves original requests; it does not launch or retry model workers."""

    def __init__(self, directory, execution_contract, *, run_id):
        self.directory = Path(directory).resolve()
        if not self.directory.is_dir() or not isinstance(run_id, str) or not run_id:
            raise ValueError("A private spool directory and frozen run ID are required")
        self.execution_contract = json.loads(json.dumps(execution_contract, allow_nan=False))
        self.run_id = run_id
        self.execution_contract["transport"] = {
            "version": "durable_spool.v1",
            "run_id": run_id,
            "directory": str(self.directory),
        }

    def _key(self, call_id):
        if type(call_id) is not str or not call_id:
            raise ValueError("Original call ID required")
        return canonical_hash({"run_id": self.run_id, "call_id": call_id})

    def __call__(self, system, request, call_id):
        key = self._key(call_id)
        path = self.directory / (key + ".request.json")
        intent = {
            "schema": "disastertrace.spool_request.v1",
            "call_id": call_id,
            "run_id": self.run_id,
            "system": system,
            "request": request,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        request, sort_keys=True, separators=(",", ":"), allow_nan=False
                    ),
                },
            ],
            "execution_sha256": canonical_hash(self.execution_contract),
        }
        if path.exists():
            previous = read(path)
            if {k: v for k, v in previous.items() if k != "dispatched_wall_ns"} != intent:
                raise ValueError("Call ID already binds a different request")
        else:
            publish(path, {**intent, "dispatched_wall_ns": time.time_ns()})
        raise PendingExecution({"remote_id": key, "request_sha256": digest(path)})

    def resolve(self, ticket, call_id):
        key = self._key(call_id)
        request_path = self.directory / (key + ".request.json")
        if ticket != {"remote_id": key, "request_sha256": digest(request_path)}:
            raise ValueError("Pending ticket differs from original durable request")
        request = read(request_path)
        if request["execution_sha256"] != canonical_hash(self.execution_contract):
            raise ValueError("Spool execution identity changed")
        response_path = self.directory / (key + ".response.json")
        if not response_path.exists():
            raise PendingExecution(ticket)
        response = read(response_path)
        fields = {
            "schema",
            "call_id",
            "request_sha256",
            "execution_sha256",
            "raw",
            "raw_sha256",
            "input_tokens",
            "output_tokens",
            "compute_seconds",
            "ended_with_eos",
            "worker_receipt_sha256",
        }
        if (
            set(response) != fields
            or response["schema"] != "disastertrace.spool_response.v1"
            or response["call_id"] != call_id
            or response["request_sha256"] != ticket["request_sha256"]
            or response["execution_sha256"] != request["execution_sha256"]
            or type(response["raw"]) is not str
            or hashlib.sha256(response["raw"].encode()).hexdigest() != response["raw_sha256"]
            or not isinstance(response["worker_receipt_sha256"], str)
            or len(response["worker_receipt_sha256"]) != 64
        ):
            raise ValueError("Remote response does not bind the original dispatched request")
        worker_path = self.directory / (key + ".worker.json")
        if digest(worker_path) != response["worker_receipt_sha256"]:
            raise ValueError("Worker receipt hash mismatch")
        worker = read(worker_path)
        bound = fields - {"schema", "worker_receipt_sha256"}
        if any(worker.get(field) != response[field] for field in bound):
            raise ValueError("Worker receipt differs from transport response")
        delivered_path = self.directory / (key + ".delivery.json")
        observed = {
            "request_sha256": ticket["request_sha256"],
            "response_sha256": digest(response_path),
        }
        if not delivered_path.exists():
            try:
                publish(delivered_path, {**observed, "observed_wall_ns": time.time_ns()})
            except FileExistsError:
                pass
        delivered = read(delivered_path)
        if any(delivered.get(k) != value for k, value in observed.items()):
            raise ValueError("Delivered response identity changed")
        elapsed = (delivered["observed_wall_ns"] - request["dispatched_wall_ns"]) / 1_000_000_000
        return response["raw"], {
            "input_tokens": response["input_tokens"],
            "output_tokens": response["output_tokens"],
            "seconds": response["compute_seconds"],
            "elapsed_seconds": elapsed,
            "ended_with_eos": response["ended_with_eos"],
            "request_file_sha256": ticket["request_sha256"],
            "response_file_sha256": digest(response_path),
            "worker_receipt_sha256": response["worker_receipt_sha256"],
            "timing_basis": "controller dispatch to observed durable response; compute separately measured by worker",
        }


class CommittedSpoolBackend(SpoolBackend):
    """Stage an outbox entry; workers require a durable controller checkpoint."""

    def __init__(self, directory, execution_contract, *, run_id):
        super().__init__(directory, execution_contract, run_id=run_id)
        self.execution_contract["transport"]["version"] = "checkpoint_committed_spool.v2"

    def commit_checkpoint(self, path):
        from .execution import execution_identity

        selector = "pending_selector" in read(Path(path))["payload"]
        return self._commit_original_checkpoint(
            path,
            pending_field="pending_selector" if selector else "pending_predictor",
            identity=execution_identity(self),
            config_field="execution_contract",
            request_encoding="system_request" if selector else "messages",
            call_field="call_id",
        )

    def _commit_original_checkpoint(
        self, path, *, pending_field, identity, config_field, request_encoding, call_field
    ):
        path = Path(path).resolve()
        checkpoint = read(path)
        payload = checkpoint["payload"]
        if canonical_hash(payload) != checkpoint["sha256"]:
            raise ValueError("Controller checkpoint integrity mismatch")
        pending = payload.get(pending_field)
        if pending is None:
            raise ValueError("Only an original pending invocation can release a worker")
        if payload["config"].get(config_field) != identity:
            raise ValueError("Controller and worker execution identity differ")
        call_id = pending[call_field]
        key = self._key(call_id)
        request_path = self.directory / (key + ".request.json")
        request = read(request_path)
        bound_request = (
            request["messages"]
            if request_encoding == "messages"
            else {"system": request["system"], "request": request["request"]}
            if request_encoding == "system_request"
            else request["request"]
        )
        expected = {
            "request_sha256": canonical_hash(bound_request),
            "execution_sha256": canonical_hash(identity),
        }
        if (
            pending["binding"] != expected
            or pending["ticket"] != {"remote_id": key, "request_sha256": digest(request_path)}
            or request["execution_sha256"] != canonical_hash(self.execution_contract)
        ):
            raise ValueError("Checkpoint does not bind the staged request")
        ready = {
            "schema": "disastertrace.spool_ready.v2",
            "call_id": call_id,
            "request_sha256": digest(request_path),
            "execution_sha256": request["execution_sha256"],
            "checkpoint_path": str(path),
            "checkpoint_file_sha256": digest(path),
            "checkpoint_payload_sha256": checkpoint["sha256"],
        }
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        ready_path = self.directory / (key + ".ready.json")
        if ready_path.exists():
            if read(ready_path) != ready:
                raise ValueError("Staged request already binds another committed checkpoint")
        else:
            publish(ready_path, ready)
        return ready

    def claim_ready(self, call_id, *, worker_id):
        """One local worker claim; a crashed claim is retained and never retried."""
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("Explicit worker identity required")
        key = self._key(call_id)
        request_path = self.directory / (key + ".request.json")
        ready_path = self.directory / (key + ".ready.json")
        if not ready_path.exists():
            raise PendingExecution({"remote_id": key, "request_sha256": digest(request_path)})
        ready, request = read(ready_path), read(request_path)
        if (
            ready["request_sha256"] != digest(request_path)
            or ready["execution_sha256"] != canonical_hash(self.execution_contract)
            or ready["checkpoint_file_sha256"] != digest(Path(ready["checkpoint_path"]))
            or ready["call_id"] != call_id
        ):
            raise ValueError("Committed request or checkpoint changed before worker claim")
        claim = {
            "worker_id": worker_id,
            "call_id": call_id,
            "request_sha256": digest(request_path),
            "ready_sha256": digest(ready_path),
            "claimed_wall_ns": time.time_ns(),
        }
        publish(self.directory / (key + ".claim.json"), claim)
        return request

    def resolve(self, ticket, call_id):
        key = self._key(call_id)
        if ticket != {
            "remote_id": key,
            "request_sha256": digest(self.directory / (key + ".request.json")),
        }:
            raise ValueError("Pending ticket differs from the committed original request")
        claim_path = self.directory / (key + ".claim.json")
        if not claim_path.exists():
            raise PendingExecution(ticket)
        claim = read(claim_path)
        if (
            claim["call_id"] != call_id
            or claim["request_sha256"] != ticket["request_sha256"]
            or claim["ready_sha256"] != digest(self.directory / (key + ".ready.json"))
        ):
            raise ValueError("Worker claim differs from the original committed request")
        return super().resolve(ticket, call_id)
