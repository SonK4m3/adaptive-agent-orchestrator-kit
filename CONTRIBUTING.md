# Contributing

Keep the two skill directories self-contained and behaviorally aligned. If changing shared instructions or diagrams, update both copies and run the package validator. Keep role TOML namespaced `ao_*`; do not overwrite upstream generic role IDs or user config.

For policy changes, add/update scenarios that test both selection and failure boundaries. Distinguish structural checks from live Codex execution and from comparative benchmarks. Report model/runtime-dependent tests as unverified unless run on that runtime.

Before opening a pull request, run:

```sh
python3 eval/validate-kit.py
python3 -m unittest discover -s tests -v
python3 scripts/build_release.py
```

Keep local execution logs, credentials, and user repositories out of the package. See `docs/RELEASING.md` for the release checklist.
