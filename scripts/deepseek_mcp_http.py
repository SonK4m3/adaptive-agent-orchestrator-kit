"""Shared loopback Streamable HTTP MCP service with an optional task dashboard."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from deepseek_jobs import JobStore, default_job_root
from deepseek_mcp import JobManager, MAX_TIMEOUT_SECONDS, MAX_WAIT_SECONDS

UI_URI = "ui://adaptive-agent-orchestrator/deepseek-dashboard.html"


def create_server(workspace_root: Path, job_root: Path | None = None, worker_script: Path | None = None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("HTTP MCP mode requires the optional 'mcp' Python package") from exc

    workspace_root = workspace_root.expanduser().resolve(strict=True)
    if not workspace_root.is_dir():
        raise ValueError("workspace root must be a directory")
    manager = JobManager(JobStore(job_root or default_job_root()),
                         worker_script or Path(__file__).with_name("deepseek_worker.py"))
    app = FastMCP("adaptive-agent-orchestrator-deepseek", host="127.0.0.1", port=8765,
                  streamable_http_path="/mcp", json_response=True,
                  instructions="Local shared DeepSeek job service. Tasks run from an allowlisted workspace snapshot; inspect patches before applying.")
    html = (Path(__file__).resolve().parents[1] / "mcp_apps" / "deepseek_dashboard.html").read_text(encoding="utf-8")
    @app.resource(UI_URI, name="DeepSeek task dashboard", mime_type="text/html;profile=mcp-app",
                  meta={"ui": {"prefersBorder": True}})
    def dashboard_resource() -> str:
        return html

    @app.tool(description="Start a bounded DSH job from the configured workspace snapshot.",
               meta={"ui": {"resourceUri": UI_URI}})
    def deepseek_task_start(task: str, input_paths: list[str], permission_mode: str = "read-only",
                            timeout_seconds: int = MAX_TIMEOUT_SECONDS) -> dict:
        return manager.start(task=task, input_paths=input_paths, workspace=str(workspace_root),
                             permission_mode=permission_mode, timeout_seconds=timeout_seconds)

    @app.tool(description="Read task status and sanitized progress.", meta={"ui": {"resourceUri": UI_URI}})
    def deepseek_task_status(task_id: str) -> dict:
        return manager.status(task_id)

    @app.tool(description="List recent task status summaries.", meta={"ui": {"resourceUri": UI_URI}})
    def deepseek_task_list(limit: int = 50) -> dict:
        return {"jobs": manager.list(limit)}

    @app.tool(description="Wait up to 30 seconds and return status.", meta={"ui": {"resourceUri": UI_URI}})
    def deepseek_task_wait(task_id: str, wait_seconds: int = 0) -> dict:
        return manager.wait(task_id, min(MAX_WAIT_SECONDS, max(0, wait_seconds)))

    @app.tool(description="Read a bounded task result and artifact paths.", meta={"ui": {"resourceUri": UI_URI}})
    def deepseek_task_result(task_id: str) -> dict:
        return manager.result(task_id)

    @app.tool(description="Cancel a task owned by this shared service.", meta={"ui": {"resourceUri": UI_URI}})
    def deepseek_task_cancel(task_id: str) -> dict:
        return manager.cancel(task_id)

    @app.tool(description="Continue a persisted DSH session inside its original workspace.",
               meta={"ui": {"resourceUri": UI_URI}})
    def deepseek_task_followup(task_id: str, task: str, timeout_seconds: int = MAX_TIMEOUT_SECONDS) -> dict:
        record = manager.store.get(task_id)
        if Path(record["source_workspace"]).resolve() != workspace_root:
            raise ValueError("task is outside the configured workspace")
        return manager.call("deepseek_task_followup", {"task_id": task_id, "task": task,
                            "timeout_seconds": min(MAX_TIMEOUT_SECONDS, max(1, timeout_seconds))})

    def close() -> None:
        manager.close()
    return app, close


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--job-root", type=Path, default=default_job_root())
    parser.add_argument("--worker-script", type=Path, default=Path(__file__).with_name("deepseek_worker.py"))
    args = parser.parse_args(argv)
    try:
        app, close = create_server(args.workspace_root, args.job_root, args.worker_script)
        try:
            app.run(transport="streamable-http")
        finally:
            close()
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"deepseek HTTP MCP startup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
