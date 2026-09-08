"""Freeze three fresh live units and independently verify their separate diagnostics."""

import argparse
import subprocess

from acp_common import CPU_PYTHON, FACTORS, HERE, PROJECT, runtime_env

from disastertrace.local_eval.storage import digest, now, read, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factor", choices=FACTORS, required=True)
    parser.add_argument("--deadline", required=True)
    args = parser.parse_args()
    if read(HERE / "inherited_acceptance_verified.json")["status"] != "passed":
        raise ValueError("inherited verification required")
    unit = HERE / "units" / args.factor
    observed = unit / "live_preparation"
    observed.mkdir(exist_ok=False)
    target = unit / "execution_live"
    run = PROJECT / "work" / ("p5-qwen3-" + args.factor.replace("_", "-") + "-v1")
    base = [CPU_PYTHON, "-m", "disastertrace.stress_eval.cli"]
    report_args = [
        "--execution",
        str(target),
        "--run",
        str(unit / "live_diagnostic"),
        "--output",
        str(unit / "live_diagnostic_report"),
    ]
    commands = [
        (
            "freeze",
            base
            + [
                "freeze",
                "--parent",
                str(HERE.parent / "p4_constrained_output_v1/execution_live"),
                "--dataset",
                str(unit / "dataset"),
                "--output",
                str(target),
                "--live",
                "--run-path",
                str(run),
                "--deadline-utc",
                args.deadline,
            ],
        ),
        (
            "diagnostic",
            base
            + [
                "collect",
                "--execution",
                str(target),
                "--output",
                str(unit / "live_diagnostic"),
                "--diagnostic",
            ],
        ),
        ("report", base + ["report"] + report_args),
        ("verify_report", base + ["report"] + report_args + ["--verify"]),
    ]
    for step, command in commands:
        source = PROJECT / "src" if step == "freeze" else target / "implementation_source/src"
        started = now()
        write(
            observed / (step + "_intent.json"),
            {
                "command": command,
                "source": str(source),
                "started_at": started,
            },
        )
        log = observed / (step + ".log")
        with log.open("xb") as output:
            result = subprocess.run(
                command,
                cwd=PROJECT,
                env=runtime_env(source, observed / "cache"),
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
            )
        write(
            observed / (step + "_result.json"),
            {
                "command": command,
                "started_at": started,
                "finished_at": now(),
                "exit_code": result.returncode,
                "log_sha256": digest(log),
            },
        )
        print({"factor": args.factor, "step": step, "exit_code": result.returncode}, flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    report = read(unit / "live_diagnostic_report/report.json")
    old = read(unit / "diagnostic_report/report.json")
    if (
        not report["complete"]
        or report["received"] != 540
        or report["origin"] != "diagnostic_stress_fixture"
        or report["local_model_calls"] != 0
        or report["methods"] != old["methods"]
        or report["errors"] != old["errors"]
    ):
        raise ValueError("live-freeze diagnostics differ from accepted offline scores")
    write(
        observed / "completion.json",
        {
            "status": "passed",
            "at": now(),
            "factor": args.factor,
            "execution_id": report["execution_id"],
            "audit_id": report["audit_id"],
            "model_calls": 0,
            "diagnostic_responses": report["received"],
            "same_method_scores_as_offline": True,
        },
    )


if __name__ == "__main__":
    main()
