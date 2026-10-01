# Contributing

Keep both skills/ directories self-contained and behaviorally aligned. Update both policy/resource copies; the validator checks their equivalence. Keep shared roles namespaced ao_* in profiles/adaptive/codex/agents. Profile configuration controls resources, never a mandatory topology. See guides/UPSTREAM-COMPARISON.md for preserved differences.

For policy changes, add/update scenarios that test both selection and failure boundaries. Distinguish structural checks from live Codex execution and from comparative benchmarks. Report model/runtime-dependent tests as unverified unless run on that runtime.

Before opening a pull request, run:

```sh
python3 scripts/build_release.py
python3 scripts/validate_package.py
python3 -m unittest discover -s tests -v
```

Keep local execution logs, credentials, and user repositories out of the package. See `guides/RELEASING.md` for the release checklist.
