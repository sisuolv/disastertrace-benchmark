"""Create an exclusive review copy containing only frozen P6 source/resources/runs/reports."""

import argparse
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    project = bundle.parents[1]
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(bundle / "execution", args.output / "execution")
    shutil.copytree(bundle / "reports", args.output / "reports")
    for mode in ("correct", "invalid-control"):
        shutil.copytree(project / "work/p6-offline-v1/runs" / mode, args.output / "runs" / mode)
    shutil.copyfile(bundle / "verify_portable.py", args.output / "verify_portable.py")
    print({"copied_to": str(args.output.resolve()), "model_weights_copied": False}, flush=True)


if __name__ == "__main__":
    main()
