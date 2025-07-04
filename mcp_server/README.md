# Neo4j MCP Proxy Server

⚠️ **Note**: This README is outdated. Please see [MCP_README.md](MCP_README.md) for current documentation.

## Current Implementation

The active MCP server is now `neo4j_mcp_lightweight.py`, which provides both Neo4j access and ML-powered search with 85%+ accuracy:

### Tools

1. **read-neo4j-cypher**
   - Execute Cypher read queries
   - Parameters:
     - `query` (string): Cypher read query
     - `params` (dict, optional): Query parameters

2. **write-neo4j-cypher**
   - Execute Cypher write/update queries
   - Parameters:
     - `query` (string): Cypher update query
     - `params` (dict, optional): Query parameters

3. **get-neo4j-schema**
   - Retrieve database schema information
   - No parameters required
   - Returns: Node labels, relationships, constraints, indexes, and properties

## Configuration

The server is configured in Claude Desktop's config file located at:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/claude/claude_desktop_config.json`

### Configuration Example

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "/opt/anaconda3/bin/python3",
      "args": [
        "/path/to/mcp_server/neo4j_exact_proxy.py"
      ],
      "cwd": "/path/to/knowledge",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "your-password",
        "NEO4J_DATABASE": "neo4j"
      }
    }
  }
}
```

## Environment Variables

The server uses the following environment variables:

- `NEO4J_URI`: Neo4j connection URI (default: `bolt://localhost:7687`)
- `NEO4J_USERNAME`: Neo4j username (default: `neo4j`)
- `NEO4J_PASSWORD`: Neo4j password (required)
- `NEO4J_DATABASE`: Neo4j database name (default: `neo4j`)

## Files

- `neo4j_exact_proxy.py` - The active MCP server implementation
- `server.py` - Original server implementation (deprecated)
- `check_neo4j_data.py` - Utility to verify Neo4j connection and data
- `archive/` - Contains previous implementations and experiments

## Testing

To test the server locally:
```bash
NEO4J_PASSWORD=your-password python neo4j_exact_proxy.py
```

The server will connect to Neo4j and wait for MCP protocol commands via stdin.

## Example Usage in Claude Desktop

Once configured, you can use these tools in Claude Desktop:

1. **Read queries**:
   ```
   Use read-neo4j-cypher to find all Document nodes
   ```

2. **Schema inspection**:
   ```
   Use get-neo4j-schema to show me the database structure
   ```

3. **Write operations**:
   ```
   Use write-neo4j-cypher to create a new node with label Test
   ```