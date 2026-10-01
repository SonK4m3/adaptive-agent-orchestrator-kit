"""Read-only runtime capability inspection: help/version/local generated schemas only.

Never login, infer, invoke a model, inspect credentials, or dump environment values.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess


def inspect_runtime(cli, home, evidence, env, profile):
    report = {"blockers": [], "roles_exposed": "unconfirmed; app metadata is not CLI evidence",
              "profile_resolution": "unconfirmed", "profile_keys": [],
              "auth_env_capabilities": [], "resume_supported": False}
    if not cli:
        report["blockers"].append("Codex CLI unavailable")
        return report
    commands = {"version": ["--version"], "exec-help": ["exec", "--help"],
                "resume-help": ["exec", "resume", "--help"], "login-help": ["login", "--help"]}
    outputs = {}
    for name, arguments in commands.items():
        result = subprocess.run([cli, *arguments], env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=15, check=False)
        outputs[name] = result.stdout
        (evidence / (name + ".txt")).write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode and name != "resume-help":
            report["blockers"].append(name + " failed")
    report["version"] = outputs["version"].strip()
    report["resume_supported"] = all(flag in outputs["resume-help"] for flag in
                                     ("SESSION_ID", "--model", "--strict-config", "--json"))
    for flag in ("--profile", "--strict-config", "--json", "--model", "--sandbox"):
        if flag not in outputs["exec-help"]:
            report["blockers"].append("Installed exec help lacks " + flag)
    # Local runtime binary identifiers establish capability, not authentication.
    # No credential file or environment value is opened/printed here.
    executable = Path(cli)
    if executable.suffix.lower() in (".exe", ""):
        binary = executable.read_bytes()
        for name in ("CODEX_API_KEY", "CODEX_ACCESS_TOKEN"):
            if name.encode("ascii") in binary:
                report["auth_env_capabilities"].append(name)
        report["auth_capability_evidence"] = "local executable identifier; authenticated acceptance unconfirmed"
    schema_dir = evidence / "runtime-schema"
    try:
        result = subprocess.run([cli, "app-server", "generate-json-schema", "--experimental", "--out", str(schema_dir)],
                                env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20, check=False)
        (evidence / "schema-generation.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    except (OSError, subprocess.SubprocessError) as exc:
        report["schema_generation"] = "unavailable: " + type(exc).__name__
        result = None
    config_schemas = []
    if result is not None and result.returncode == 0:
        for path in schema_dir.rglob("*.json"):
            if "ConfigReadResponse" in path.name or path.name == "config.schema.json":
                config_schemas.append((path, json.loads(path.read_text(encoding="utf-8"))))
    # Prefer config schema beside the installed binary when shipped by the runtime.
    adjacent = executable.parent / "config.schema.json"
    if adjacent.is_file():
        config_schemas.append((adjacent, json.loads(adjacent.read_text(encoding="utf-8"))))
    def find_property(schema, parts):
        while "$ref" in schema:
            ref = schema["$ref"]
            if not ref.startswith("#/"):
                return None
            target = document
            for key in ref[2:].split("/"):
                target = target.get(key, {})
            schema = target
        if not parts:
            return schema
        return find_property(schema.get("properties", {}).get(parts[0], {}), parts[1:]) if parts[0] in schema.get("properties", {}) else None
    def leaves(data, prefix=()):
        for key, value in data.items():
            if isinstance(value, dict):
                yield from leaves(value, (*prefix, key))
            else:
                yield (*prefix, key), value
    for parts, value in leaves(profile):
        matched = None
        for path, document in config_schemas:
            schema = document.get("definitions", {}).get("Config", document)
            definition = find_property(schema, parts)
            if definition is not None:
                matched = {"source": path.name,
                           "schema_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "definition": definition}
                break
        entry = {"key": ".".join(parts), "status": "schema-unavailable; strict runtime check pending"}
        if matched:
            entry.update(status="key recognized in local runtime schema", schema=matched)
        # Generated app-server Config is permissive and currently omits agents.
        # A permissive additionalProperties is NOT proof a runtime key is valid.
        report["profile_keys"].append(entry)
    report["profile_validation"] = ("local schema keys checked; strict-config invocation still required"
                                    if all(e["status"].startswith("key recognized") for e in report["profile_keys"])
                                    else "incomplete: installed protocol schema omits some profile keys; --strict-config gates live invocation")
    report["documented_profile_reference"] = "https://learn.chatgpt.com/docs/agent-configuration/subagents"
    report["named_roles"] = sorted(p.stem for p in (home / "agents").glob("ao_*.toml"))
    return report
