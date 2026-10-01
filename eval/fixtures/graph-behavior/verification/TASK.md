# Authorization boundary

R1: authorize(role, action) in auth.py returns True only for admin reading/writing,
or viewer reading. Every other combination returns False.
R2: Deny nonstring inputs, empty values, case variants, unknown roles/actions and
objects pretending to compare equal to valid strings. Exact built-in strings only.
R3: Deny unknown actions even for admin; no implicit privilege escalation.
R4: The function has no side effects and does not mutate arguments.

Implementation task: only auth.py and optional graph.json, graph-record.json,
graph-1.json, graph-2.json may change. Report coverage and regression evidence.
For a read-only assessment requested by the harness, preserve auth.py and identify
defects with requirement IDs, auth.py/authorize references and concrete evidence.
