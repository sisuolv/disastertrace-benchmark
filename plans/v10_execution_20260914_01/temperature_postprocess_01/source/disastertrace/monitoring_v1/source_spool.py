"""Checkpoint-committed native source transport with no model invocation."""

import json

from .source_execution import source_identity
from .spool_backend import CommittedSpoolBackend


class ArchiveSpoolSource:
    def __init__(self, directory, source_contract, *, run_id):
        self._transport = CommittedSpoolBackend(directory, source_contract, run_id=run_id)
        self.source_contract = json.loads(json.dumps(self._transport.execution_contract))
        self.directory = self._transport.directory

    def __call__(self, request, receipt_id):
        return self._transport(
            "Registered native archive query; no model invocation.", request, receipt_id
        )

    def resolve(self, ticket, receipt_id):
        raw, details = self._transport.resolve(ticket, receipt_id)
        if details["input_tokens"] != 0 or details["output_tokens"] != 0:
            raise ValueError("A native source worker cannot bill model tokens")
        return json.loads(raw), details

    def commit_checkpoint(self, path):
        return self._transport._commit_original_checkpoint(
            path,
            pending_field="pending_source",
            identity=source_identity(self),
            config_field="source_execution_contract",
            request_encoding="request",
            call_field="receipt_id",
        )

    def claim_ready(self, receipt_id, *, worker_id):
        return self._transport.claim_ready(receipt_id, worker_id=worker_id)
