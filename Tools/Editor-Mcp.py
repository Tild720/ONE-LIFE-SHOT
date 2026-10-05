"""Local-only transport for the engine-native editor MCP server."""
import json
import sys
import urllib.request
from pathlib import Path

ENDPOINT = 'http://127.0.0.1:8000/mcp'
SESSION = Path(__file__).resolve().parents[1] / 'One_life_Shot/Saved/McpSession.txt'

def request(method, params, session=None):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if session:
        headers['Mcp-Session-Id'] = session
    req = urllib.request.Request(ENDPOINT, json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode(), headers)
    with urllib.request.urlopen(req, timeout=180) as response:
        raw = response.read().decode()
        if response.headers.get('Mcp-Session-Id'):
            SESSION.write_text(response.headers['Mcp-Session-Id'])
        return json.loads(raw)

def call(toolset, tool, arguments):
    return request('tools/call', {'name':'call_tool','arguments':{'toolset_name':toolset,'tool_name':tool,'arguments':arguments}}, SESSION.read_text().strip())

if __name__ == '__main__':
    if sys.argv[1] == 'init':
        result = request('initialize', {'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'Codex','version':'1.0'}})
    elif sys.argv[1] == 'describe':
        result = request('tools/call', {'name':'describe_toolset','arguments':{'toolset_name':sys.argv[2]}}, SESSION.read_text().strip())
    else:
        result = call(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv)>3 else {})
    print(json.dumps(result, ensure_ascii=True))
