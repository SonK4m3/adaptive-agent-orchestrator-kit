# Duration grouping

Implement the two public interfaces in duration.py and grouping.py using only Python stdlib.

R1: parse_duration(text) returns integer seconds for a trimmed ASCII decimal integer
followed immediately by lowercase s, m or h. Leading zeros and zero are valid.
R2: Nonstrings raise TypeError. Invalid syntax (including Unicode digits, sign,
fraction, embedded whitespace, exponent, uppercase units), or a result greater
than 9007199254740991 seconds, raises ValueError. Avoid accepting bool as text.
R3: group_by_status(records) accepts a list of dicts with string id and status.
Return a list of {status: str, ids: list[str]} groups ordered by first appearance.
Preserve ID order and duplicates; empty strings and __proto__ are ordinary values.
R4: Reject nonlists and any malformed record with TypeError. Do not mutate inputs.
R5: summarize(records) in grouping.py accepts a list of dicts containing string id,
status and duration. Use parse_duration from duration.py; return first-appearance
groups {status, ids, seconds}, summing durations per status. Invalid input raises
the same boundary exceptions as the two underlying interfaces. Never mutate input.

Only duration.py, grouping.py and optional graph.json, graph-record.json,
graph-1.json, graph-2.json may change. Report requirement coverage and evidence.
