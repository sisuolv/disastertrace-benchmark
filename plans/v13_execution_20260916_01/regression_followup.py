"""Fresh regression for the documented A03 tail-disposition amendment."""

import sys

import regression

regression.OUT = regression.RUN / "regression_02"

if __name__ == "__main__":
    if sys.argv[1:] == ["prepare"]:
        regression.prepare()
    elif sys.argv[1:] == ["execute"]:
        regression.execute()
    else:
        raise SystemExit("Use prepare or execute for the new amendment directory")
