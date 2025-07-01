# MCP Neo4j Integration

This document describes the new MCP (Model Context Protocol) Neo4j integration that allows direct comparison between our custom retrievers and the Neo4j MCP tool's query capabilities.

## Overview

The MCP Neo4j integration adds a new search type called `mcp_cypher` (or `neo4j_mcp`) to the Knowledge Graph API. This allows you to execute queries through the MCP protocol and compare results with our existing search methods.

## Features

### 1. New Search Type: `mcp_cypher`

The API now supports a new search type that uses the MCP protocol to query Neo4j:

```python
# Example API call
response = requests.post(
    "http://localhost:8000/search",
    json={
        "query": "What is the minimum balance for a Foreign Currency Account?",
        "search_type": "mcp_cypher",  # or "neo4j_mcp"
        "top_k": 5,
        "use_reranking": True
    }
)
```

### 2. Enhanced Natural Language to Cypher Translation

The enhanced MCP client includes sophisticated pattern matching for common query types:

- **Balance queries**: Minimum balance, account balance requirements
- **Interest rate queries**: Interest rates, swap rates
- **Fee queries**: Fees, charges, costs (including international transfers)
- **Product queries**: Account opening, term deposits, loan eligibility
- **Process queries**: How-to guides, procedures, steps
- **Requirement queries**: Eligibility criteria, requirements

### 3. Direct Cypher Query Execution

Execute Cypher queries directly through the MCP endpoint:

```python
# Direct Cypher query
response = requests.post(
    "http://localhost:8000/mcp/cypher",
    json={
        "query": "MATCH (c:Chunk)-[:BELONGS_TO]->(d:Document) WHERE c.text =~ '(?i).*minimum.*balance.*' RETURN c.text, d.filename LIMIT 5",
        "parameters": {"limit": 5}
    }
)
```

### 4. MCP Status Check

Check the MCP Neo4j connection status:

```python
response = requests.get("http://localhost:8000/mcp/status")
# Returns: {"status": "connected", "mcp_server": "mcp-neo4j-cypher", "node_count": 12345}
```

## Configuration

The MCP Neo4j connection is configured with:
- **URI**: bolt://localhost:7687
- **Username**: neo4j
- **Password**: knowledge123

These can be overridden using environment variables:
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

## Testing

### Run Comparison Tests

Use the provided test script to compare search methods:

```bash
# Compare a single query across all search types
python test_mcp_neo4j.py --query "What is the minimum balance requirement?"

# Run full test suite
python test_mcp_neo4j.py --full-test

# Execute direct Cypher query
python test_mcp_neo4j.py --cypher "MATCH (n:Document) RETURN n.filename LIMIT 10"
```

### Run with Test Runner

The standard test runner now supports MCP search types:

```bash
python run_tests.py --search-type mcp_cypher --use-reranking
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│   API Client    │────▶│  Knowledge API   │────▶│  MCP Client │
└─────────────────┘     └──────────────────┘     └─────────────┘
                                                          │
                                                          ▼
                                                  ┌──────────────┐
                                                  │    Neo4j     │
                                                  │   Database   │
                                                  └──────────────┘
```

## Implementation Details

### Files Added/Modified

1. **`docker/mcp_neo4j_client.py`**: Base MCP client implementation
2. **`docker/enhanced_mcp_client.py`**: Enhanced client with NL to Cypher translation
3. **`docker/api.py`**: Updated to support new search type and MCP endpoints
4. **`knowledge_test_agent/test_mcp_neo4j.py`**: Test script for MCP functionality
5. **`knowledge_test_agent/run_tests.py`**: Updated to include MCP search types

### Query Translation Examples

The enhanced MCP client translates natural language queries to optimized Cypher:

| Natural Language Query | Generated Cypher Pattern |
|------------------------|--------------------------|
| "minimum balance" | Searches for chunks containing balance requirements with relevance boosting |
| "interest rate swap" | Targets IRS-specific documents and content |
| "international transfer fees" | Focuses on international fee-related content |
| "how to open account" | Prioritizes procedural content with numbered steps |

## Performance Considerations

- The MCP client uses direct Neo4j connections for optimal performance
- Query patterns are optimized with relevance boosting based on content type
- Results are scored based on semantic density and pattern matches
- The enhanced client caches important terms extraction for repeated queries

## Future Enhancements

1. **Real MCP Protocol**: Replace direct Neo4j connection with actual MCP protocol communication
2. **Query Caching**: Add result caching for frequently executed queries
3. **Advanced NLP**: Integrate more sophisticated NLP for query understanding
4. **Query Optimization**: Add query plan analysis and optimization
5. **Federated Search**: Combine MCP results with other search methods dynamically

## Troubleshooting

### MCP Connection Issues

If you see connection errors:
1. Ensure Neo4j is running: `docker ps | grep neo4j`
2. Check credentials in environment variables
3. Verify network connectivity to Neo4j

### Query Translation Issues

If queries aren't returning expected results:
1. Check the generated Cypher query in the response metadata
2. Test the Cypher query directly using the `/mcp/cypher` endpoint
3. Review the query patterns in `enhanced_mcp_client.py`

## Conclusion

The MCP Neo4j integration provides a powerful way to compare our custom retrievers with direct Neo4j queries through the MCP protocol. This enables:

- Direct performance comparisons
- Query optimization insights
- Alternative retrieval strategies
- Enhanced debugging capabilities

Use this integration to evaluate and improve the knowledge retrieval system's effectiveness.