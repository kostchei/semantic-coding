"""Regression: child search must not consume the MCP protocol input stream."""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class TransportTests(unittest.TestCase):
    def test_search_child_receives_eof_while_protocol_stays_open(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            bootstrap = Path(directory) / 'server.py'
            bootstrap.write_text(f'''
import sys
sys.path.insert(0, {str(root)!r})
import mcp_server
import semcode.grepai_runner as grepai_runner
import semcode.pipeline as pipeline
original_run = grepai_runner.subprocess.run
def fake_search(command, **kwargs):
    kwargs['timeout'] = 2
    return original_run([sys.executable, '-c', "import sys; sys.stdin.read(); print('[]')"], **kwargs)
grepai_runner.subprocess.run = fake_search
grepai_runner.find_binary = lambda *a, **kw: 'fixture'
grepai_runner.get_lmstudio_token = lambda: ''
pipeline.resolve_project = lambda **kw: ({directory!r}, {directory!r}, 'fixture', None)
import telemetry.collector
telemetry.collector.log_interaction = lambda **kw: None
mcp_server.mcp.run(transport='stdio')
''', encoding='utf-8')

            async def check():
                async with stdio_client(StdioServerParameters(command=sys.executable, args=[str(bootstrap)])) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool('search_codebase', {'query': 'fixture'})
                        self.assertFalse(result.isError, result)
                        tools = await session.list_tools()
                        self.assertTrue(any(tool.name == 'search_codebase' for tool in tools.tools))
            asyncio.run(check())
