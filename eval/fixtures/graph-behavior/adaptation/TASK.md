# Currency conversion, revision 1

R1: convert(value) in convert.py accepts nonnegative finite int or float values
(excluding bool) in USD and returns integer cents. Use Decimal(str(value)) for
decimal interpretation. Fractional cents are rounded half up in revision 1.
R2: Reject nonnumeric, negative, nonfinite values and bool with TypeError.
R3: After implementing and verifying revision 1, pause for user acceptance at the
checkpoint specified in the harness prompt. Do not finish beyond that checkpoint.

Only convert.py, checkpoint.json and optional graph.json, graph-record.json,
graph-1.json, graph-2.json may change. Report revision, requirements and evidence.
