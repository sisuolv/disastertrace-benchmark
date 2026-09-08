# Offline CI template

`offline.workflow.yml` contains the prepared GitHub Actions workflow. It runs CPU
regression tests, fresh offline builds and reconstruction of the actual P4 report.
It never generates model answers. The frozen 44-test P4 backend suite requires
the exact historical vLLM environment, so its previously executed evidence is
retained separately from CPU CI.

The current GitHub OAuth credential has `repo`, `read:org` and `gist` scopes, but
does not have `workflow`. Code/document uploads are supported. This template is
published as documentation; it is not an active GitHub Actions workflow and no
cloud CI success is claimed. Enabling it later requires GitHub workflow write
permission and placing it at the repository root `.github/workflows/offline.yml`.

The local checkout also retains the prepared workflow at that path. Its exclusion
from the current upload does not delete or alter earlier local work.
