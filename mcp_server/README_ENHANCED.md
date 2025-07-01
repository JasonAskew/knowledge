# Enhanced Knowledge Graph MCP Server

This enhanced MCP server provides a unified interface to the Knowledge Graph system with integrated Neo4j MCP functionality and streaming support.

## Features

1. **Internal Neo4j MCP Integration**: The server internally handles Neo4j MCP calls, so clients only need to configure our knowledge MCP server
2. **Streaming Support**: Long responses can be streamed for better user experience
3. **Multiple Search Types**: 
   - `vector`: Vector similarity search
   - `graph`: Graph-based search
   - `hybrid`: Combined vector and graph search
   - `text2cypher`: Natural language to Cypher conversion
   - `neo4j_cypher`: Direct Cypher execution through Neo4j MCP
   - `neo4j_schema`: Schema-aware search using Neo4j MCP

## Installation

1. Install dependencies:
```bash
pip install -r requirements_enhanced.txt
```

2. Set up environment variables:
```bash
export API_BASE_URL="http://localhost:8000"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="your_password"
export NEO4J_DATABASE="neo4j"
```

## Claude Desktop Configuration

Update your Claude Desktop configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "enhanced-knowledge-graph": {
      "command": "python",
      "args": ["-m", "mcp_server.enhanced_server"],
      "cwd": "/path/to/knowledge/system",
      "env": {
        "API_BASE_URL": "http://localhost:8000",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "your_password",
        "NEO4J_DATABASE": "neo4j"
      },
      "features": {
        "streaming": true
      }
    }
  }
}
```

## Usage Examples

### 1. Regular Search with Streaming
```
Use the search_knowledge tool with query "minimum balance requirements" and stream=true
```

### 2. Direct Neo4j Cypher Query
```
Use the search_knowledge tool with:
- query: "MATCH (d:Document) RETURN d.filename LIMIT 5"
- search_type: "neo4j_cypher"
- stream: true
```

### 3. Schema-Aware Search
```
Use the search_knowledge tool with:
- query: "Show me the graph schema"
- search_type: "neo4j_schema"
```

### 4. Execute Cypher Directly
```
Use the execute_cypher tool with:
- query: "MATCH (n:Chunk)-[:SIMILAR_TO]-(m:Chunk) RETURN n.text, m.text LIMIT 5"
- stream: true
```

### 5. Get Neo4j Schema
```
Use the get_neo4j_schema tool with stream=true
```

## Architecture

The enhanced server acts as a proxy that:

1. **Handles standard knowledge graph queries** through the existing API
2. **Internally manages Neo4j MCP connections** without requiring separate client configuration
3. **Provides streaming responses** for large result sets
4. **Unifies different search types** under a single interface

## Key Components

1. **EnhancedKnowledgeGraphMCPServer**: Main server class with streaming support
2. **Neo4jMCPClient**: Manages Neo4j connections through our proxy
3. **Neo4jMCPProxy**: Lightweight Neo4j interaction layer (no external dependencies)

## Benefits

1. **Single Configuration**: Clients only need to configure our MCP server
2. **Transparent Neo4j Access**: Neo4j MCP functionality is available without separate setup
3. **Streaming Support**: Better handling of large responses
4. **Unified Interface**: All search types accessible through one tool

## Troubleshooting

1. **Neo4j Connection Issues**: 
   - Ensure Neo4j is running and accessible
   - Check credentials and URI
   - Verify the database name

2. **Streaming Not Working**:
   - Ensure Claude Desktop supports streaming (check version)
   - Verify the "features": {"streaming": true} is set in config

3. **Import Errors**:
   - Install neo4j driver: `pip install neo4j`
   - Ensure all dependencies are installed

## Development

To run the server standalone for testing:

```bash
python -m mcp_server.enhanced_server
```

For debugging, set logging level:
```bash
export LOG_LEVEL=DEBUG
python -m mcp_server.enhanced_server
```