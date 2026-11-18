from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@unittest.skipUnless(importlib.util.find_spec("mcp"), "optional MCP SDK is not installed")
class SharedHttpServerTests(unittest.TestCase):
    def test_http_server_is_loopback_and_pins_workspace_for_start_tool(self):
        from deepseek_mcp_http import UI_URI, create_server

        with tempfile.TemporaryDirectory() as temp:
            app, close = create_server(Path(temp))
            try:
                self.assertEqual(app.settings.host, "127.0.0.1")
                self.assertEqual(app.settings.streamable_http_path, "/mcp")
                tools = asyncio.run(app.list_tools())
                start = next(tool for tool in tools if tool.name == "deepseek_task_start")
                self.assertNotIn("workspace", start.inputSchema.get("properties", {}))
                self.assertEqual(start.meta["ui"]["resourceUri"], UI_URI)
                resources = asyncio.run(app.list_resources())
                self.assertIn(UI_URI, [str(resource.uri) for resource in resources])
            finally:
                close()


if __name__ == "__main__":
    unittest.main()
