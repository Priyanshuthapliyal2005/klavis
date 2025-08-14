# Perplexity MCP Server

A Model Context Protocol (MCP) server that proxies requests to the Perplexity AI chat API. Implemented in TypeScript and packaged for local (npm) and containerized (Docker) usage.

## Features

- Exposes Perplexity tools via MCP: ask, research, reason, code_assistant, summary
- Supports Streamable HTTP (`/mcp`) and SSE (`/sse`, `/messages`) transports

## Prerequisites

- Node.js 18+ and npm (for local install)
- Docker (optional, for containerized runs)
- A Perplexity API key (set as `PERPLEXITY_API_KEY`)

There is a `.env.example` in this folder you can copy to `.env` and edit.

## Environment variables

- PERPLEXITY_API_KEY - required. The Perplexity API token used for requests.
- PORT - optional. Defaults to `5000`.

Example `.env` (copy from `.env.example`):

```
PERPLEXITY_API_KEY=your-perplexity-key-here
PORT=5000
```

## Configure `mcp.json` to point to this server

If you use the workspace `mcp.json` (example location: `.vscode/mcp.json`), add or update the `perplexity` entry to point to the running server and include the `x-auth-token` header with your key. For example:

```jsonc
{
  "servers": {
    "perplexity": {
      "type": "http",
      "url": "http://localhost:5000/mcp",
      "headers": {
        "x-auth-token": "your-perplexity-key-here"
      }
    }
  }
}
```

Replace the token above with your `PERPLEXITY_API_KEY` or an environment-secure secret.

## Run locally (traditional - npm)

1. Change to the server directory and install dependencies:

```bash
cd mcp_servers/perplexityAI
npm ci
```

2. Create `.env` from the example and set your key:

```bash
cp .env.example .env
# edit .env and set PERPLEXITY_API_KEY
```

3. Build and start:

```bash
npm run build
npm start
```

Server will listen on `http://localhost:5000` by default.

## Run with Docker (from repository root)

1. Build the image (run from repo root):

```bash
docker build -t perplexity-mcp-server:latest mcp_servers/perplexityAI
```

2. Run the container (use the `.env` file in the folder to pass the API key):

```bash
docker run --env-file mcp_servers/perplexityAI/.env -p 5000:5000 perplexity-mcp-server:latest
```

The container exposes port `5000` which maps to the MCP `url` shown in the `mcp.json` example above.

## Notes and troubleshooting

- If you see authentication errors, verify the `PERPLEXITY_API_KEY` value and that you send it in the `x-auth-token` header.
- Use `PORT` environment variable to change the listening port; update `mcp.json` accordingly.
- For local development, `stdio` transport may be used by some hosts; this server supports HTTP+SSE/Streamable HTTP.

## Enjoy

Start the server using your preferred method (npm or Docker), update your `mcp.json` `perplexity` section to point to the running server, and enjoy integrating Perplexity tools via MCP.

@Priyanshuthapliyal2005