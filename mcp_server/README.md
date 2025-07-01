# Knowledge Graph MCP Server

This is an MCP (Model Context Protocol) server that provides access to the Knowledge Graph System with GraphRAG capabilities.

## Features

- **Search Knowledge Base**: Search using vector, graph, hybrid, or text2cypher methods
- **Direct Cypher Queries**: Execute Cypher queries on the Neo4j graph
- **Document Management**: List and retrieve document information
- **Resource Access**: Direct access to document content

## Installation

### For Development

```bash
cd mcp_server
pip install -e .
```

### For Production

```bash
pip install .
```

## Usage

### Running the Server

```bash
knowledge-graph-mcp
```

Or using Python directly:

```bash
python -m mcp_server.server
```

### Available Tools

1. **search_knowledge**: Search the knowledge graph
   - Parameters:
     - `query` (required): Search query
     - `search_type`: "vector", "graph", "hybrid", or "text2cypher" (default: "hybrid")
     - `limit`: Maximum results (default: 5)
     - `rerank`: Enable reranking (default: true)

2. **query_cypher**: Execute Cypher queries
   - Parameters:
     - `query` (required): Cypher query string

3. **get_document_info**: Get document metadata
   - Parameters:
     - `document_name` (required): Document filename

4. **list_documents**: List all documents
   - Parameters:
     - `limit`: Maximum documents to return (default: 50)

## Claude Desktop Configuration

Add this to your Claude Desktop configuration file:

### macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
### Windows: `%APPDATA%\Claude\claude_desktop_config.json`
### Linux: `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "knowledge-graph-mcp",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "your-password",
        "API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Environment Variables

The server requires the following environment variables:

- `NEO4J_URI`: Neo4j connection URI (default: bolt://localhost:7687)
- `NEO4J_USER`: Neo4j username (default: neo4j)
- `NEO4J_PASSWORD`: Neo4j password
- `API_BASE_URL`: Base URL for the Knowledge API (default: http://localhost:8000)

## Docker Support

To run the MCP server in Docker:

```bash
docker build -f Dockerfile.mcp -t knowledge-mcp .
docker run -p 5000:5000 \
  -e NEO4J_URI=bolt://neo4j:7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=password \
  knowledge-mcp
```

## Example Usage in Claude

Once configured, you can use the knowledge graph in Claude Desktop:

```
Use the knowledge-graph tool to search for information about minimum account balances
```

```
Query the knowledge graph for all documents related to foreign exchange options
```

```
Execute a Cypher query to find all entities related to interest rates
```