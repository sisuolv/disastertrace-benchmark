"""Retain isolation; separately record urllib3's denied IPv6 loopback capability probe."""

import argparse
import hashlib
import json
import os
import runpy
import socket
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--isolation-root", type=Path, required=True)
    parser.add_argument("--blocked-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-spec", type=Path, required=True)
    args = parser.parse_args()
    execution = args.execution.resolve()
    isolation = args.isolation_root.resolve()
    blocked = tuple(p.resolve() for p in args.blocked_root)
    if not execution.is_relative_to(isolation) or not args.output.resolve().is_relative_to(
        isolation
    ):
        raise ValueError("copied execution and receipt must stay inside isolation root")
    if any(name == "disastertrace" or name.startswith("disastertrace.") for name in sys.modules):
        raise ValueError("task imported before isolation")
    attempts = {"original_path": 0, "network": 0, "subprocess": 0, "forbidden_import": 0}
    import_probes = []

    def guard(event, values):
        if event in ("open", "os.listdir", "os.scandir") and values:
            value = values[0]
            if isinstance(value, (str, bytes, os.PathLike)):
                path = Path(os.fsdecode(value)).resolve()
                if not path.is_relative_to(isolation) and any(
                    path.is_relative_to(p) for p in blocked
                ):
                    attempts["original_path"] += 1
                    raise PermissionError("original project/model path blocked")
        if event == "socket.bind" and values[1] == ("::1", 0):
            caller = sys._getframe(1)
            if (
                caller.f_globals.get("__name__") == "urllib3.util.connection"
                and caller.f_code.co_name == "_has_ipv6"
            ):
                import_probes.append(
                    {
                        "event": event,
                        "module": "urllib3.util.connection",
                        "function": "_has_ipv6",
                        "address": ["::1", 0],
                        "operation_permitted": False,
                        "dependency_file_sha256": hashlib.sha256(
                            Path(caller.f_code.co_filename).read_bytes()
                        ).hexdigest(),
                    }
                )
                raise PermissionError("IPv6 loopback capability probe remains blocked")
        if event in ("socket.connect", "socket.getaddrinfo", "socket.bind", "socket.sendto"):
            attempts["network"] += 1
            raise PermissionError("network blocked")
        if event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.fork"):
            attempts["subprocess"] += 1
            raise PermissionError("child processes blocked")
        if event == "import" and values[0].split(".")[0] in ("torch", "vllm", "tensorflow", "flax"):
            attempts["forbidden_import"] += 1
            raise PermissionError("model backend imports blocked")

    sys.addaudithook(guard)
    for root in blocked:
        try:
            (root / "__p7_denied_read_probe__").read_bytes()
        except PermissionError:
            pass
        else:
            raise RuntimeError("original path guard did not fire")
    with socket.socket() as probe:
        try:
            probe.connect(("127.0.0.1", 9))
        except PermissionError:
            pass
        else:
            raise RuntimeError("network guard did not fire")
    try:
        subprocess.run(["__p7_never_executed__"], check=False)
    except PermissionError:
        pass
    else:
        raise RuntimeError("subprocess guard did not fire")
    probes = dict(attempts)
    if probes != {
        "original_path": len(blocked),
        "network": 1,
        "subprocess": 1,
        "forbidden_import": 0,
    }:
        raise ValueError("isolation self-tests differ")
    attempts.update({k: 0 for k in attempts})
    source_root = execution / "source"
    sys.path[:] = [str(source_root)] + [
        p for p in sys.path if p and not any(Path(p).resolve().is_relative_to(b) for b in blocked)
    ]
    os.chdir(isolation)
    cli_exits = []
    commands = [("--help",), ("verify", "--execution", str(execution))]
    specs = json.loads(args.review_spec.read_text())
    for spec in specs:
        commands.append(("verify-report", "--execution", str(execution), "--run-root",
                         str(isolation / spec["run"]), "--output", str(isolation / spec["report"])))
    for arguments in commands:
        sys.argv = ["disastertrace.forecast_live", *arguments]
        try:
            runpy.run_module("disastertrace.forecast_live", run_name="__main__")
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise
            cli_exits.append(0)
        else:
            cli_exits.append(0)
    modules = {
        name: module.__file__
        for name, module in sys.modules.items()
        if (name == "disastertrace" or name.startswith("disastertrace."))
        and getattr(module, "__file__", None)
    }
    if not modules or any(
        not Path(p).resolve().is_relative_to(source_root) for p in modules.values()
    ):
        raise ValueError("task imported outside copied source closure")
    if any(attempts.values()) or any(
        name in sys.modules for name in ("torch", "vllm", "tensorflow", "flax")
    ):
        raise ValueError("unexpected original access, network or model backend")
    if len(import_probes) != 1:
        raise ValueError("bound optional-import probe count differs")
    record = json.loads((execution / "execution.json").read_text())
    manifest = json.loads((execution / "manifest.json").read_text())
    receipt = {
        "schema_version": "forecast_live_cpu_relocation_v1",
        "status": "passed",
        "execution_id": record["execution_id"],
        "package_id": manifest["package_id"],
        "source_files": record["source_files"],
        "cli_exits": cli_exits,
        "isolation_mechanism": "Python audit hook installed before task import; subprocesses also blocked",
        "guard_self_tests": probes,
        "unexpected_blocked_attempts": attempts,
        "blocked_optional_import_probes": import_probes,
        "source_modules": modules,
        "model_generations": 0,
        "torch_and_vllm_loaded": False,
        "original_project_and_weights_blocked": True,
        "network_blocked": True,
    }
    with args.output.open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": "passed", "receipt": str(args.output), "cli_exits": cli_exits}))


if __name__ == "__main__":
    main()
