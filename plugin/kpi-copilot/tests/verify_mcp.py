"""Exercise the real stdio transport against a fictional, offline workspace."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

def data(result):
    return result.structuredContent or json.loads(result.content[0].text)

async def main():
    with tempfile.TemporaryDirectory(prefix='kpi-mcp-test-') as tmp:
        fixture = Path(tmp) / 'fixture'
        shutil.copytree(ROOT / 'examples' / 'northwind-board', fixture)
        cache = fixture / 'northwind-q3' / 'cache'
        cache.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture / 'board.json', cache / 'board.json')
        server = StdioServerParameters(command=sys.executable, args=[str(ROOT / 'scripts' / 'mcp_server.py')],
                                       env={**os.environ, 'KPI_PROFILE': str(fixture / 'profile.yaml')})
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 8
                result = await session.call_tool('projects', {})
                assert not result.isError and 'northwind-q3' in str(result)
                result = await session.call_tool('prepare_kpis', {'project':'northwind-q3','offline':True})
                assert not result.isError, str(result)
                assert data(result)['ok'], str(result)
                review = await session.call_tool('read_review', {'project':'northwind-q3'})
                assert data(review)['queue']['rubric']
                preview = await session.call_tool('preview_pms', {'project':'northwind-q3'})
                assert data(preview)['approval_digest']
                refused = await session.call_tool('send_approved_kpis', {'project':'northwind-q3','approved_payload_digest':'wrong'})
                assert refused.isError
                refused = await session.call_tool('read_review', {'project':'../other'})
                assert refused.isError
                assert list((fixture/'northwind-q3').glob('KPI Tracker*.xlsx'))
    print('MCP stdio verified: discovery, offline run, judgement queue, preview and refusal checks.')

if __name__ == '__main__':
    asyncio.run(main())
