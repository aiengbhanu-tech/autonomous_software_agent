# Contributing

Run `python -m unittest discover -s tests -v` and
`python -m forgefix verify-benchmark` before submitting changes.

Sandbox changes also require the opt-in Docker integration suite. A green mock
test is not evidence of a working isolation boundary. Never add a host execution
fallback or an unreviewed model-controlled command capability.

Benchmark changes must include manually specified expected outputs, a broken
version, a reference fix, public/hidden separation, and a new suite version when
the semantics change. Do not combine scripted-oracle and live-model scores.

