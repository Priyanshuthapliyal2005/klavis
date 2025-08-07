# Perplexity MCP Server

A Model Context Protocol (MCP) server for Perplexity AI, implemented in TypeScript.

## Features

- Exposes Perplexity tools via MCP: Ask, Research, Reason
- Endpoints:
  - `/sse` - Server-Sent Events endpoint for real-time communication
  - `/messages/` - SSE message handling endpoint
  - `/mcp` - StreamableHTTP endpoint for direct API calls

## Setup

### Prerequisites
- Node.js 18+ and npm
- Perplexity API key

### Installation

1. Install dependencies:
   ```bash
   npm install
   ```
2. Copy `.env.example` to `.env` and set your `PERPLEXITY_API_KEY`.
3. Build and run:
   ```bash
   npm run build
   npm start
   ```

### Docker

1. Build the Docker image:
   ```bash
   docker build -t perplexity-mcp-server .
   ```
2. Run the container:
   ```bash
   docker run -e PERPLEXITY_API_KEY=your_key -p 5000:5000 perplexity-mcp-server
   ```

## API Endpoints

- `/sse` - Server-Sent Events endpoint for real-time communication
- `/messages/` - SSE message handling endpoint
- `/mcp` - StreamableHTTP endpoint for direct API calls

## Tool Usage Examples

### Ask
```json
{
  "name": "perplexity_ask",
  "arguments": {
    "messages": [
      { "role": "user", "content": "What is the capital of France?" }
    ]
  }
}
```

### Research
```json
{
  "name": "perplexity_research",
  "arguments": {
    "messages": [
      { "role": "user", "content": "Explain quantum computing." }
    ]
  }
}
```

### Reason
```json
{
  "name": "perplexity_reason",
  "arguments": {
    "messages": [
      { "role": "user", "content": "Why is the sky blue?" }
    ]
  }
}
```

## License

This project follows the same license as the parent Klavis project.
