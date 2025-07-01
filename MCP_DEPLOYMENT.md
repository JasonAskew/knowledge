# MCP Deployment Guide for Knowledge Graph System

This guide covers deploying the Knowledge Graph System with MCP (Model Context Protocol) support for Claude Desktop integration.

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Local Deployment](#local-deployment)
4. [Production Deployment](#production-deployment)
5. [Claude Desktop Configuration](#claude-desktop-configuration)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

## Overview

The Knowledge Graph MCP Server provides Claude Desktop with direct access to your knowledge base through the Model Context Protocol. This enables:

- Natural language search across documents
- Text-to-Cypher query generation
- Direct graph database queries
- Document retrieval and analysis

## Prerequisites

- Python 3.9+
- Docker and Docker Compose (for containerized deployment)
- Neo4j database running
- Knowledge Graph API deployed and accessible

## Local Deployment

### 1. Start the Knowledge Graph API

First, ensure your Knowledge Graph API is running:

```bash
cd docker
docker-compose up -d
```

Verify the API is accessible:
```bash
curl http://localhost:8000/stats
```

### 2. Install MCP Server

```bash
cd mcp_server
./setup.sh
```

This will:
- Create a virtual environment
- Install dependencies
- Display configuration for Claude Desktop

### 3. Test MCP Server

Run the server manually to verify it works:

```bash
source venv/bin/activate
python -m mcp_server.standalone_server
```

## Production Deployment

### 1. Using Docker Compose

Add the MCP service to your `docker-compose.yml`:

```yaml
services:
  # ... existing services ...
  
  mcp-server:
    build:
      context: ..
      dockerfile: docker/Dockerfile.mcp
    environment:
      - API_BASE_URL=http://knowledge-api:8000
    ports:
      - "5000:5000"
    depends_on:
      - knowledge-api
    networks:
      - knowledge-network
```

### 2. Deploy with Docker

```bash
# Build and start all services
docker-compose up -d

# Check MCP server logs
docker-compose logs mcp-server
```

### 3. Using Kubernetes

Create a deployment for the MCP server:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowledge-mcp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: knowledge-mcp
  template:
    metadata:
      labels:
        app: knowledge-mcp
    spec:
      containers:
      - name: mcp-server
        image: knowledge-mcp:latest
        env:
        - name: API_BASE_URL
          value: "http://knowledge-api-service:8000"
        ports:
        - containerPort: 5000
---
apiVersion: v1
kind: Service
metadata:
  name: knowledge-mcp-service
spec:
  selector:
    app: knowledge-mcp
  ports:
  - port: 5000
    targetPort: 5000
```

## Claude Desktop Configuration

### 1. Locate Configuration File

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

### 2. Add MCP Server Configuration

For local deployment:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "/path/to/knowledge/mcp_server/venv/bin/python",
      "args": ["-m", "mcp_server.standalone_server"],
      "cwd": "/path/to/knowledge/mcp_server",
      "env": {
        "API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

For remote deployment:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "/path/to/knowledge/mcp_server/venv/bin/python",
      "args": ["-m", "mcp_server.standalone_server"],
      "cwd": "/path/to/knowledge/mcp_server",
      "env": {
        "API_BASE_URL": "https://your-api-domain.com"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

After updating the configuration, restart Claude Desktop for changes to take effect.

## Testing

### 1. Verify MCP Server in Claude

In Claude Desktop, you should see "knowledge-graph" in the available tools. Test with:

```
Use the knowledge-graph tool to search for "minimum account balance"
```

### 2. Test Different Search Types

```
Use knowledge-graph to search for "foreign exchange" using text2cypher search
```

```
Get statistics about the knowledge base using knowledge-graph
```

### 3. Monitor Logs

Check MCP server logs for any issues:

```bash
# Local deployment
tail -f mcp_server.log

# Docker deployment
docker-compose logs -f mcp-server
```

## Troubleshooting

### MCP Server Not Appearing in Claude

1. Check configuration file syntax
2. Ensure paths are absolute, not relative
3. Verify Python executable path is correct
4. Check Claude Desktop logs

### Connection Errors

1. Verify API is accessible:
   ```bash
   curl http://localhost:8000/stats
   ```

2. Check firewall settings
3. Ensure correct API_BASE_URL in environment

### Search Not Working

1. Verify Neo4j is running
2. Check API logs for errors
3. Ensure documents are ingested

### Performance Issues

1. Enable API caching
2. Increase MCP server resources
3. Use connection pooling for Neo4j

## Security Considerations

### 1. API Authentication

For production, add authentication to your API:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "python",
      "args": ["-m", "mcp_server.standalone_server"],
      "env": {
        "API_BASE_URL": "https://api.example.com",
        "API_KEY": "your-secure-api-key"
      }
    }
  }
}
```

### 2. Network Security

- Use HTTPS for production deployments
- Implement rate limiting
- Use VPN for sensitive data

### 3. Access Control

- Limit MCP server to specific users
- Implement document-level permissions
- Audit access logs

## Monitoring

### 1. Health Checks

Add health check endpoint to MCP server:

```python
@server.tool_handler
async def handle_health_check() -> TextContent:
    """Check system health"""
    # Implementation
```

### 2. Metrics

Monitor:
- Query response times
- Error rates
- Resource usage
- Active connections

### 3. Alerts

Set up alerts for:
- API downtime
- High error rates
- Performance degradation

## Next Steps

1. **Enhance Security**: Implement authentication and encryption
2. **Add Features**: Extended document analysis, multi-modal search
3. **Scale**: Implement caching, load balancing
4. **Monitor**: Set up comprehensive monitoring and alerting

For questions or issues, please refer to the main documentation or create an issue in the repository.