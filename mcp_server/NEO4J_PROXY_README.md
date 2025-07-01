# Neo4j MCP Proxy Server

This implementation provides an MCP server that acts as a transparent proxy to the `mcp-neo4j-cypher` MCP tool, allowing Claude Desktop to execute Neo4j Cypher queries through our custom MCP server.

## Overview

The proxy server:
1. Acts as an MCP client to `mcp-neo4j-cypher`
2. Forwards all `neo4j_cypher` tool calls to the actual Neo4j MCP server
3. Returns the Neo4j MCP server's responses transparently
4. Provides fallback to direct Neo4j connection if subprocess fails

## Implementation Files

### 1. `neo4j_proxy_simple.py`
The main proxy server implementation that:
- Spawns `mcp-neo4j-cypher` as a subprocess
- Handles MCP protocol communication
- Provides the `neo4j_cypher` tool to Claude Desktop
- Falls back to direct Neo4j connection if needed

### 2. `mcp_neo4j_proxy.py`
An alternative implementation using the MCP client library (requires additional dependencies).

### 3. `neo4j_proxy_server.py`
Another implementation variant with different subprocess handling.

## Configuration

### Claude Desktop Configuration

Add this to your Claude Desktop configuration file:

```json
{
  "mcpServers": {
    "neo4j-proxy": {
      "command": "python",
      "args": ["/Users/jaskew/workspace/Skynet/claude/knowledge/mcp_server/neo4j_proxy_simple.py"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "knowledge123"
      }
    }
  }
}
```

### Environment Variables

The proxy server uses these environment variables:
- `NEO4J_URI`: Neo4j connection URI (default: `bolt://localhost:7687`)
- `NEO4J_USER`: Neo4j username (default: `neo4j`)
- `NEO4J_PASSWORD`: Neo4j password (default: `knowledge123`)

## Testing

Run the test script to verify the proxy is working:

```bash
cd /Users/jaskew/workspace/Skynet/claude/knowledge/mcp_server
python test_neo4j_proxy.py
```

The test script will:
1. Test direct Neo4j connection
2. Start the proxy server
3. Test tool listing
4. Execute sample Cypher queries

## Usage in Claude Desktop

Once configured, you can use the `neo4j_cypher` tool in Claude Desktop exactly as you would with the direct `mcp-neo4j-cypher` integration:

```
Use the neo4j_cypher tool to execute this query:
MATCH (d:Document) 
RETURN d.filename as filename, d.total_pages as pages 
LIMIT 10
```

## Architecture

```
Claude Desktop
     |
     v
neo4j-proxy (MCP Server)
     |
     v
mcp-neo4j-cypher (subprocess)
     |
     v
Neo4j Database
```

## Troubleshooting

1. **Subprocess fails to start**: The proxy will automatically fall back to direct Neo4j connection
2. **Authentication errors**: Check that environment variables are set correctly
3. **Connection errors**: Ensure Neo4j is running and accessible at the configured URI

## Benefits

1. **Transparency**: Provides the exact same interface as `mcp-neo4j-cypher`
2. **Reliability**: Includes fallback to direct connection
3. **Flexibility**: Can add custom logic or logging if needed
4. **Compatibility**: Works with existing Claude Desktop configurations