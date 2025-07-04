# MCP Server for Knowledge Graph System

This directory contains MCP (Model Context Protocol) servers that provide Neo4j database access and advanced search capabilities to Claude Desktop.

## 🚀 Current Implementation

The active MCP server is **`neo4j_mcp_optimized.py`** - an optimized server that defaults to fast keyword search with optional vector search and reranking capabilities.

### Key Features

- **<0.2 second query time** - Default keyword search is extremely fast
- **Flexible search options** - Choose between speed and accuracy
- **Full Neo4j access** - Read/write Cypher queries and schema inspection
- **Entity search** - New tool for finding specific entities and their documents
- **Smart keyword extraction** - Better handling of common query patterns

## 📦 Available Servers

### 1. `neo4j_mcp_optimized.py` (CURRENT - RECOMMENDED)
- **Status**: Active, Production-ready
- **Features**: Fast keyword search by default, optional vector/reranking
- **Query time**: <0.2s (keyword), ~5s (vector)
- **Accuracy**: 80%+ (keyword), 88%+ (vector + reranking)
- **Best for**: Claude Desktop with instant responses

### 2. `neo4j_mcp_lightweight.py`
- **Status**: Previous version, still functional
- **Features**: Lazy loading, always uses vector search
- **Startup**: <1 second
- **Query time**: 5-6 seconds per search
- **Issue**: Slow for interactive use

### 3. `neo4j_enhanced_search.py`
- **Status**: Full-featured but heavy
- **Features**: All search methods, immediate model loading
- **Issue**: Startup timeout in Claude Desktop
- **Use case**: Direct Python usage, not MCP

### 4. `neo4j_exact_proxy.py`
- **Status**: Basic, limited functionality
- **Features**: Pure Neo4j proxy only
- **Accuracy**: 18.75% (Cypher-only search)
- **Use case**: When only Cypher access is needed

## 🛠️ Tools Provided

### 1. **read_neo4j_cypher**
Execute Cypher read queries against the Neo4j database.

```json
{
  "query": "MATCH (d:Document) RETURN d.filename LIMIT 5",
  "params": {}
}
```

### 2. **write_neo4j_cypher**
Execute Cypher write/update queries.

```json
{
  "query": "CREATE (n:TestNode {name: $name}) RETURN n",
  "params": {"name": "test"}
}
```

### 3. **get_neo4j_schema**
Retrieve comprehensive database schema information.

Returns:
- Node labels and counts
- Relationship types
- Constraints and indexes
- Property information

### 4. **search_documents** (Enhanced servers only)
Flexible search with speed/accuracy tradeoff options.

```json
{
  "query": "minimum balance requirements for savings accounts",
  "top_k": 10,
  "use_vector_search": false,  // Default: fast keyword search
  "use_reranking": false       // Requires vector search
}
```

### 5. **search_entities** (Optimized server only)
Find specific entities and their documents.

```json
{
  "entity_text": "interest rate",
  "community_id": null,  // Optional: filter by community
  "limit": 10
}
```

## ⚙️ Configuration

### Claude Desktop Configuration

Edit the config file at:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

### Example Configuration

```json
{
  "mcpServers": {
    "knowledge-graph-search": {
      "command": "/opt/anaconda3/bin/python3",
      "args": [
        "/path/to/knowledge/mcp_server/neo4j_mcp_optimized.py"
      ],
      "cwd": "/path/to/knowledge",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "knowledge123",
        "NEO4J_DATABASE": "neo4j",
        "PYTHONPATH": "/path/to/knowledge"
      }
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USERNAME` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | Required | Neo4j password |
| `NEO4J_DATABASE` | `neo4j` | Database name |
| `PYTHONPATH` | Required | Path to project root |

## 🧪 Testing

### Test Connection
```bash
cd mcp_server
NEO4J_PASSWORD=knowledge123 python neo4j_mcp_lightweight.py
```

### Verify in Claude Desktop
After configuration, restart Claude Desktop and try:
```
Use the search_documents tool to find information about "foreign currency accounts"
```

### Check Logs
If issues occur, check Claude Desktop logs:
```bash
# macOS
cat ~/Library/Logs/Claude/mcp*.log
```

## 📊 Performance Comparison

| Server | Startup Time | Query Time | Search Accuracy | Memory Usage |
|--------|--------------|------------|-----------------|--------------|
| `neo4j_mcp_optimized.py` | <1s | 0.2s / 5s | 80% / 88%+ | Low (lazy) |
| `neo4j_mcp_lightweight.py` | <1s | 5-6s | 85-90% | Medium |
| `neo4j_enhanced_search.py` | 10-15s | 2-3s | 85-90% | High |
| `neo4j_exact_proxy.py` | <1s | 0.1s | 18.75% | Minimal |

## 🔧 Troubleshooting

### Server Won't Start
1. Check Neo4j is running: `docker ps | grep neo4j`
2. Verify Python path in config
3. Check Claude Desktop logs for errors
4. Ensure PYTHONPATH is set correctly

### Timeout Issues
- Use `neo4j_mcp_lightweight.py` instead of enhanced version
- Check network connectivity to Neo4j
- Verify Neo4j credentials

### Search Not Working
1. Ensure models can be downloaded (internet access)
2. Check `sentence-transformers` is installed
3. Verify embedding dimensions match (384)

## 🚀 Advanced Usage

### Custom Cypher Queries
```
Use read_neo4j_cypher to run this query:
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:CONTAINS_ENTITY]->(e:Entity)
WHERE e.community_id = 5
RETURN d.filename, COUNT(DISTINCT e) as entity_count
ORDER BY entity_count DESC
LIMIT 10
```

### Community-Aware Search
The enhanced servers automatically leverage community detection:
- 42 communities detected among 10,150 entities
- Two-phase search: intra-community → bridge nodes
- Configurable community weight in search ranking

## 📝 Development

### Adding New Tools
1. Define tool with `@mcp.tool()` decorator
2. Implement async function
3. Return JSON-serializable results
4. Update this README

### Model Updates
Current models:
- **Embeddings**: `BAAI/bge-small-en-v1.5` (384 dimensions)
- **Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2`

## 📄 License

Part of the Knowledge Graph System - see main [LICENSE](../LICENSE) file.

---

**Current Version**: v0.0.1 | **Active Server**: `neo4j_mcp_optimized.py` | **Default Accuracy**: 80%+ | **Max Accuracy**: 88.8%