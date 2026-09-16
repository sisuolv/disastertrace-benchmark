"""A constrained production transport with a frozen worker/configuration manifest."""

import hashlib
import json
from pathlib import Path

from .spool_backend import CommittedSpoolBackend
from .targets import canonical_hash


class ProductionSpoolBackend(CommittedSpoolBackend):
    def __init__(self, directory, execution_contract, *, run_id, bound_files):
        if not isinstance(bound_files, dict) or not bound_files:
            raise ValueError("Production requires frozen implementation and evaluator files")
        self._bound_files_json = json.dumps(bound_files, sort_keys=True, allow_nan=False)
        contract = json.loads(json.dumps(execution_contract, allow_nan=False))
        contract["production_binding"] = {
            "version": "managed_committed_spool.v1",
            "files_sha256": canonical_hash(bound_files),
            "assurance": "frozen managed transport and worker artifacts; not arbitrary Python isolation",
        }
        super().__init__(directory, contract, run_id=run_id)
        self._configuration_hash = self._current_configuration_hash()
        self.validate_binding()

    def _current_configuration_hash(self):
        return canonical_hash(
            {
                "directory": str(self.directory),
                "run_id": self.run_id,
                "execution_contract": self.execution_contract,
                "files": json.loads(self._bound_files_json),
            }
        )

    def validate_binding(self):
        expected = {
            "directory",
            "run_id",
            "execution_contract",
            "_configuration_hash",
            "_bound_files_json",
        }
        if (
            set(vars(self)) != expected
            or self._current_configuration_hash() != self._configuration_hash
        ):
            raise ValueError("Bound production configuration changed")
        for name, digest in json.loads(self._bound_files_json).items():
            if (
                not isinstance(digest, str)
                or hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest
            ):
                raise ValueError("Bound production artifact changed")

    def __call__(self, system, request, call_id):
        self.validate_binding()
        return super().__call__(system, request, call_id)

    def resolve(self, ticket, call_id):
        self.validate_binding()
        from .spool_backend import digest, read

        key = self._key(call_id)
        recovery_valid = False
        if "api_transport_v2" in self.execution_contract:
            from .api_transport_v2 import validate_publication

            recovery_valid = validate_publication(self, call_id)
        failed = self.directory / (key + ".failure.json")
        if failed.exists():
            request_path = self.directory / (key + ".request.json")
            failure, request = read(failed), read(request_path)
            if (
                ticket != {"remote_id": key, "request_sha256": digest(request_path)}
                or failure.get("call_id") != call_id
                or failure.get("request_sha256") != ticket["request_sha256"]
                or failure.get("execution_sha256") != request["execution_sha256"]
            ):
                raise ValueError("Worker failure does not bind the original request")
            if not recovery_valid:
                raise RuntimeError("Original worker failed; execution reservation remains unknown")
        return super().resolve(ticket, call_id)

    def commit_checkpoint(self, path):
        self.validate_binding()
        from .spool_backend import digest, read

        current = read(Path(path))
        payload = current["payload"]
        if canonical_hash(payload) != current["sha256"]:
            raise ValueError("Pending checkpoint integrity mismatch")
        field = "pending_selector" if "pending_selector" in payload else "pending_predictor"
        pending = payload[field]
        ready_path = self.directory / (self._key(pending["call_id"]) + ".ready.json")
        if ready_path.exists():
            ready = read(ready_path)
            original_path = Path(ready["checkpoint_path"])
            if digest(original_path) != ready["checkpoint_file_sha256"]:
                raise ValueError("Original worker release checkpoint changed")
            original = read(original_path)["payload"]
            prefix = original["ledger"]["events"]
            if (
                payload["config"] != original["config"]
                or pending != original[field]
                or payload["ledger"]["events"][: len(prefix)] != prefix
            ):
                raise ValueError("Pending checkpoint does not extend the original release")
            # Poll checkpoints may advance the timing ledger, not release another worker.
            return super().commit_checkpoint(original_path)
        return super().commit_checkpoint(path)

    def claim_ready(self, call_id, *, worker_id):
        self.validate_binding()
        return super().claim_ready(call_id, worker_id=worker_id)
