"""Submit the single generation-disabled ACP preflight after inherited verification."""

from acp_common import HERE, PROJECT, command_for, submit

from disastertrace.local_eval.storage import digest, read


def main():
    for name in ("inherited_acceptance_verified.json", "preservation_before_acp.json"):
        if read(HERE / name)["status"] != "passed":
            raise ValueError("accepted P5 evidence and preservation required")
    directory = HERE / "acp/preflight_001"
    path = HERE / "units/revision_chain/execution_offline"
    worker = HERE / "acp_preflight.py"
    command = command_for(
        worker, directory / "request.json", path / "implementation_source/src", 1200
    )
    submit(
        directory,
        {
            "kind": "generation_disabled_preflight",
            "display_name": "dt-p5-preflight-20260908-001",
            "project": str(PROJECT),
            "execution_path": str(path),
            "worker_sha256": digest(worker),
            "common_sha256": digest(HERE / "acp_common.py"),
            "command": command,
            "model_calls": 0,
            "maximum_gpus": 1,
        },
    )


if __name__ == "__main__":
    main()
