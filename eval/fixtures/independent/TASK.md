# Independent coding slices

Implement both modules with no external dependencies. Keep exports unchanged.

R1: parseDuration accepts strings containing a nonnegative integer followed by s, m or h, with optional surrounding whitespace. Convert to integer seconds. Units are lowercase. Zero is valid.
R2: Non-string duration throws TypeError. Invalid syntax, negative/decimal numbers, unsupported units, or results outside Number.MAX_SAFE_INTEGER throw RangeError.
R3: groupByStatus accepts an array of records with string status and string id. Return an array of {status, ids} groups, in first-seen status order. Preserve ID order and duplicates. Treat __proto__ as an ordinary status.
R4: Reject a non-array or any invalid record with TypeError. Do not mutate input records or arrays.

Only duration.mjs and grouping.mjs may change. Verification is held in the kit's eval/oracles/independent.test.mjs. Report requirement coverage and actual agent count. This is a synthetic orchestration fixture, not a production benchmark.
