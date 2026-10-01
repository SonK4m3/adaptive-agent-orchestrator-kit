# Named dispatch pilot — 2026-10-01

Status: failed worker artifact check; named dispatch/closure unverified. Overall runtime gate blocked. Requested root: gpt-6.1-sol / medium, Codex CLI 0.159.2, Windows, temporary CODEX_HOME, named adaptive preset, 600-second budget. Existing user config hash was identical before/after; credentials were opted into a private ephemeral copy, never published.

Raw evidence on the build machine: dist/graph-20261001T160349Z-3fb50040ac5644379eea2fd965b902ca/. CLI session ID: 01a0f835-389b-70b0-a0d3-ac678117f219. Reviewed results:

- Elapsed: 78.478 seconds, no timeout; only allowed scratch paths considered, no source artifact changed.
- External label check failed: label.txt remained Draft rather than Ready. Exit code zero from the CLI did not establish completion.
- Candidate messages item_1/item_3/item_4 report policy-blocked file reads/checks and unavailable graph/IDs/close tools. Rejection tool payloads themselves are not in this public JSONL; the exact policy cause is not independently diagnosed.
- item_2 records one completed wait, empty receiver IDs/states. No spawn/close event was observed in this trace. Candidate prose naming ao_worker is not sufficient to establish actual role identity or completion.
- No graph record; configured named role pins and profile files exist but effective serving/concurrency remain unverified.
- Reviewer probe: unrun because the worker gate failed. Autonomous root-only/independent/verification/adaptation runs: unrun. No automatic retry or forced-topology substitution.

Prepare-only evidence: dist/graph-20261001T160302Z-ec9314eab38d40f3a202154215feec2d/. It confirms installed package inventory/help and generated schema inspection, not role serving. The generated protocol schema omits agents fields; --strict-config allowed the subsequent CLI turn to start, but profile layering/concurrency were not independently attested.

This attempt predates the final owned-process-tree and sandboxed-oracle hardening. Historical artifacts remain unchanged. Reviewed [implementation status](AGENT-GRAPH-IMPLEMENTATION-2026-10-01.md) contains offline regression evidence, measurement limits and the next required decision.
