"""External behavioral criteria. This is not an orchestration rubric or OS sandbox.

Executed outside the evaluated Git workspace, with bytecode writes disabled.
The candidate modules are synthetic and untrusted: run under the harness deadline.
"""
import argparse
import ast
import copy
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
import importlib.util
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True


def guard_source(source):
    """Bounded fixture subset; rejects measurement-tampering APIs, not a sandbox.

    OS filesystem/network isolation remains required. Unsupported candidate syntax
    must not be interpreted as a verified behavioral failure or executed anyway.
    """
    allowed_imports = {'re', 'decimal', 'math', 'duration'}
    allowed_symbols = {'re': {'fullmatch', 'match', 'search', 'compile', 'ASCII'},
                       'decimal': {'Decimal', 'InvalidOperation', 'ROUND_HALF_UP', 'ROUND_HALF_EVEN', 'localcontext'},
                       'math': {'isfinite', 'isnan', 'isinf', 'inf', 'nan', 'floor', 'ceil', 'trunc'},
                       'duration': {'parse_duration'}}
    banned = {'eval', 'exec', 'compile', 'open', 'print', 'input', 'globals', 'locals',
              'getattr', 'setattr', 'delattr', 'vars', 'dir', 'breakpoint', 'exit', 'quit',
              'sys', 'os', 'inspect', 'subprocess', 'modules', 'builtins', 'mro',
              'f_globals', 'f_locals', 'gi_frame', 'cr_frame', 'tb_frame', 'func_globals'}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import) and any(alias.name not in allowed_imports for alias in node.names):
            raise ValueError('Unsupported candidate import')
        if isinstance(node, ast.ImportFrom) and (node.level or node.module not in allowed_imports or any(
                alias.name not in allowed_symbols.get(node.module, set()) for alias in node.names)):
            raise ValueError('Unsupported candidate import')
        if isinstance(node, (ast.Import, ast.ImportFrom)) and any(
                alias.asname and (alias.asname.startswith('__') or alias.asname in banned) for alias in node.names):
            raise ValueError('Unsupported candidate import alias')
        if isinstance(node, ast.Name) and (node.id.startswith('__') or node.id in banned):
            raise ValueError('Unsupported candidate introspection or IO')
        if isinstance(node, ast.Attribute) and (node.attr.startswith('_') or node.attr in banned):
            raise ValueError('Unsupported candidate introspection or IO')
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.Global, ast.Nonlocal)):
            raise ValueError('Unsupported candidate construct')


def load(workspace, name):
    path = workspace / (name + ".py")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked candidate module: " + name)
    guard_source(path.read_text(encoding='utf-8'))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def equal(actual, expected):
    if actual != expected:
        raise AssertionError("unexpected result")


def raises(kind, function, *args):
    try:
        function(*args)
    except kind:
        return
    raise AssertionError("expected " + kind.__name__)


def evaluate(workspace, scenario, probe=None, revision=2):
    results = []
    # Guard every candidate before any module can cross-import another candidate.
    if probe != 'reviewer':
        try:
            for path in workspace.glob('*.py'):
                if path.is_symlink():
                    raise ValueError('linked candidate')
                guard_source(path.read_text(encoding='utf-8'))
        except (OSError, ValueError, SyntaxError):
            return [{'criterion': 'external-oracle', 'status': 'unrun',
                     'reason': 'Candidate outside supported oracle subset; no code executed'}]
    def criterion(name, operation):
        try:
            operation()
            results.append({"criterion": name, "status": "pass", "verification_owner": "harness",
                            "method": "external Python oracle"})
        except BaseException as exc:
            # Avoid echoing candidate-provided exception messages into shared evidence.
            results.append({"criterion": name, "status": "fail", "error_type": type(exc).__name__,
                            "verification_owner": "harness", "method": "external Python oracle"})
    if probe == "reviewer":
        def assessment():
            data = json.loads((workspace / "assessment.json").read_text(encoding="utf-8"))
            findings = data["findings"]
            if not isinstance(findings, list) or not any(
                    isinstance(f, dict) and f.get("requirement") in ("R1", "R3")
                    and f.get("path") == "auth.py" and f.get("symbol") == "authorize"
                    and isinstance(f.get("evidence"), str) and f["evidence"].strip()
                    and f.get("severity") in ("critical", "high", "medium", "low") for f in findings):
                raise AssertionError("missing requirement-linked finding")
        criterion("P3.3-assessment-artifact", assessment)
        # Actual reviewer identity/read-only behavior must be checked in the trace.
        results.append({"criterion": "P3.3-independent-reviewer-attribution", "status": "unrun",
                        "reason": "Artifact cannot establish independent author or read-only lifecycle"})
    elif scenario == "root-only":
        criterion("R1-label", lambda: equal((workspace / "label.txt").read_bytes(), b"Ready\n"))
    elif scenario == "independent":
        def duration_valid():
            parse = load(workspace, "duration").parse_duration
            for text, expected in (("90s", 90), ("2m", 120), ("3h", 10800), (" 0s ", 0),
                                   ("01m", 60), ("9007199254740991s", 9007199254740991)):
                actual = parse(text)
                equal(actual, expected)
                equal(type(actual), int)
        def duration_invalid():
            parse = load(workspace, "duration").parse_duration
            for value in (None, True, 2, {}, ["1s"]):
                raises(TypeError, parse, value)
            for value in ("", "-1s", "+1s", "1.5h", "2M", "1d", "1 s", "1e3s", "1s\n2s",
                          "１２s", "١s", "9007199254740992s", "9007199254740991h"):
                raises(ValueError, parse, value)
        def grouping():
            fn = load(workspace, "grouping").group_by_status
            equal(fn([]), [])
            equal(fn([{"id": "a", "status": "open"}, {"id": "b", "status": "done"},
                      {"id": "a", "status": "open"}, {"id": "", "status": "__proto__"}]),
                  [{"status": "open", "ids": ["a", "a"]}, {"status": "done", "ids": ["b"]},
                   {"status": "__proto__", "ids": [""]}])
        def group_negative():
            fn = load(workspace, "grouping").group_by_status
            for value in (None, {}, "records", [None], [{}], [{"id": 1, "status": "a"}],
                          [{"id": "a", "status": 1}]):
                raises(TypeError, fn, value)
            records = [{"id": "a", "status": "open"}, {"id": "b", "status": "open"}]
            before = copy.deepcopy(records)
            fn(records)
            equal(records, before)
        def integrated():
            load(workspace, "duration")
            fn = load(workspace, "grouping").summarize
            records = [{"id": "a", "status": "open", "duration": "2m"},
                       {"id": "b", "status": "__proto__", "duration": "1h"},
                       {"id": "a", "status": "open", "duration": "90s"}]
            before = copy.deepcopy(records)
            equal(fn(records), [{"status": "open", "ids": ["a", "a"], "seconds": 210},
                                {"status": "__proto__", "ids": ["b"], "seconds": 3600}])
            equal(records, before)
            equal(fn([]), [])
            for value in (None, [None], [{}], [{"id": 1, "status": "x", "duration": "1s"}],
                          [{"id": "a", "status": "x", "duration": None}]):
                raises(TypeError, fn, value)
            raises(ValueError, fn, [{"id": "a", "status": "x", "duration": "-1s"}])
        for name, fn in (("R1-duration", duration_valid), ("R2-duration-negative", duration_invalid),
                         ("R3-grouping", grouping), ("R4-grouping-negative-and-mutation", group_negative),
                         ("R5-integration", integrated)):
            criterion(name, fn)
    elif scenario == "verification":
        class Pretender:
            def __eq__(self, other):
                return True
        class Text(str):
            pass
        def matrix():
            fn = load(workspace, "auth").authorize
            roles = ["admin", "viewer", "unknown", "", "Admin", " admin", None, {}, 1, True, Pretender(), Text("admin")]
            actions = ["read", "write", "delete", "", "Read", "read ", None, {}, 1, Pretender(), Text("read")]
            for role in roles:
                for action in actions:
                    expected = type(role) is str and type(action) is str and (
                        (role == "admin" and action in ("read", "write")) or (role == "viewer" and action == "read"))
                    actual = fn(role, action)
                    equal(type(actual), bool)
                    equal(actual, expected)
        def mutation():
            fn = load(workspace, "auth").authorize
            role, action = {"role": "admin"}, ["read"]
            before = copy.deepcopy((role, action))
            equal(fn(role, action), False)
            equal((role, action), before)
        criterion("R1-R3-auth-matrix-negative", matrix)
        criterion("R4-input-mutation", mutation)
        results.append({"criterion": "R4-other-side-effects", "status": "unrun",
                        "reason": "Input checks do not establish absence of all side effects"})
    elif scenario == "adaptation":
        def conversion():
            fn = load(workspace, "convert").convert
            rounding = ROUND_HALF_UP if revision == 1 else ROUND_HALF_EVEN
            for value in (0, 1, 0.01, 1.005, 1.015, 2.225, 3.335, 100.999, 0.005):
                actual = fn(value)
                expected = int((Decimal(str(value)) * 100).quantize(Decimal(1), rounding=rounding))
                equal(type(actual), int)
                equal(actual, expected)
        def negative():
            fn = load(workspace, "convert").convert
            for value in (None, True, False, "1.00", {}, [], -1, -0.001, math.inf, -math.inf, math.nan):
                raises(TypeError, fn, value)
        criterion("R1-rounding-revision-" + str(revision), conversion)
        criterion("R2-conversion-negative", negative)
        results.append({"criterion": "R4-revision-and-handoff", "status": "unrun",
                        "reason": "Requires observed checkpoint/update and graph/trace review"})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--probe", choices=("worker", "reviewer"))
    parser.add_argument("--revision", type=int, choices=(1, 2), default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = evaluate(args.workspace, args.scenario, args.probe, args.revision)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return int(any(result["status"] == "fail" for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
