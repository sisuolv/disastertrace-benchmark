# Preserved offline validation failures

The first combined installed-backend command failed during pytest collection because P7 and P8 both use an installed_backend.py basename. No test or model generation ran in that command. Each P8 installed test had already passed in the separate three-test invocation. The second driver uses pytest importlib mode to keep both test modules distinct. The original driver, command, exit1 and log remain unchanged. Its87 core tests passed. No GPU or source-prefix claim was consumed.

The second driver passes87 core and12 combined installed-backend tests, then waits for successful P7 finalization. Its source-prefix replay runs in the project test Python, which has no transformers installation; it exits before creating the source bundle. The third driver uses the existing CPU review Python with the pinned tokenizer dependencies. No package is installed or upgraded, no source-prefix/model claim is reused, and the second failure log remains preserved.
