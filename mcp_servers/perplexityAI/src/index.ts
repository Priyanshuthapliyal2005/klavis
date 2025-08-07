#!/usr/bin/env node
import express, { Request, Response } from 'express';
// @ts-ignore
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
// @ts-ignore
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
// @ts-ignore
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
// @ts-ignore
// @ts-ignore
import { Tool, ListToolsRequestSchema, CallToolRequestSchema, CallToolRequest } from "@modelcontextprotocol/sdk/types.js";
import { AsyncLocalStorage } from "async_hooks";

const PERPLEXITY_ASK_TOOL: Tool = {
  name: "perplexity_ask",
  description:
    "Engages in a conversation using the Sonar API. Accepts an array of messages (each with a role and content) and returns a ask completion response from the Perplexity model.",
  inputSchema: {
    type: "object",
    properties: {
      messages: {
        type: "array",
        items: {
          type: "object",
          properties: {
            role: { type: "string", description: "Role of the message (e.g., system, user, assistant)" },
            content: { type: "string", description: "The content of the message" },
          },
          required: ["role", "content"],
        },
        description: "Array of conversation messages",
      },
    },
    required: ["messages"],
  },
};

const PERPLEXITY_RESEARCH_TOOL: Tool = {
  name: "perplexity_research",
  description:
    "Performs deep research using the Perplexity API. Accepts an array of messages (each with a role and content) and returns a comprehensive research response with citations.",
  inputSchema: PERPLEXITY_ASK_TOOL.inputSchema,
};

const PERPLEXITY_REASON_TOOL: Tool = {
  name: "perplexity_reason",
  description:
    "Performs reasoning tasks using the Perplexity API. Accepts an array of messages (each with a role and content) and returns a well-reasoned response using the sonar-reasoning-pro model.",
  inputSchema: PERPLEXITY_ASK_TOOL.inputSchema,
};

const PERPLEXITY_API_KEY = process.env.PERPLEXITY_API_KEY;

class PerplexityClient {
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  // Update token if needed
  refreshToken() {
    const token = getPerplexityToken();
    if (token) {
      this.apiKey = token;
      return true;
    }
    return false;
  }

  async performChatCompletion(
    messages: Array<{ role: string; content: string }>,
    model: string = "sonar-pro"
  ): Promise<string> {
    this.refreshToken();
    const url = new URL("https://api.perplexity.ai/chat/completions");
    const body = {
      model,
      messages,
    };
    let response;
    try {
      response = await fetch(url.toString(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify(body),
      });
    } catch (error) {
      throw new Error(`Network error while calling Perplexity API: ${error}`);
    }
    if (!response.ok) {
      let errorText;
      try {
        errorText = await response.text();
      } catch {
        errorText = "Unable to parse error response";
      }
      throw new Error(
        `Perplexity API error: ${response.status} ${response.statusText}\n${errorText}`
      );
    }
    let data;
    try {
      data = await response.json();
    } catch (jsonError) {
      throw new Error(`Failed to parse JSON response from Perplexity API: ${jsonError}`);
    }
    let messageContent = data.choices[0].message.content;
    if (data.citations && Array.isArray(data.citations) && data.citations.length > 0) {
      messageContent += "\n\nCitations:\n";
      data.citations.forEach((citation: string, index: number) => {
        messageContent += `[${index + 1}] ${citation}\n`;
      });
    }
    return messageContent;
  }
}

const getPerplexityMcpServer = () => {
  const server = new Server(
    {
      name: "perplexityAI-mcp-server",
      version: "0.1.0",
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [PERPLEXITY_ASK_TOOL, PERPLEXITY_RESEARCH_TOOL, PERPLEXITY_REASON_TOOL],
}));

server.setRequestHandler(CallToolRequestSchema, async (request: CallToolRequest) => {
  try {
    const { name, arguments: args } = request.params;
    if (!args) throw new Error("No arguments provided");
    
    const perplexityToken = getPerplexityToken();
    if (!perplexityToken) {
      throw new Error("No valid Perplexity token found for this instance");
    }

    const perplexityClient = new PerplexityClient(perplexityToken);
    
    switch (name) {
      case "perplexity_ask": {
        if (!Array.isArray(args.messages)) throw new Error("Invalid arguments for perplexity_ask: 'messages' must be an array");
        const result = await perplexityClient.performChatCompletion(args.messages, "sonar-pro");
        return { content: [{ type: "text", text: result }], isError: false };
      }
      case "perplexity_research": {
        if (!Array.isArray(args.messages)) throw new Error("Invalid arguments for perplexity_research: 'messages' must be an array");
        const result = await perplexityClient.performChatCompletion(args.messages, "sonar-deep-research");
        return { content: [{ type: "text", text: result }], isError: false };
      }
      case "perplexity_reason": {
        if (!Array.isArray(args.messages)) throw new Error("Invalid arguments for perplexity_reason: 'messages' must be an array");
        const result = await perplexityClient.performChatCompletion(args.messages, "sonar-reasoning-pro");
        return { content: [{ type: "text", text: result }], isError: false };
      }
      default:
        return { content: [{ type: "text", text: `Unknown tool: ${name}` }], isError: true };
    }
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error instanceof Error ? error.message : String(error)}`,
        },
      ],
      isError: true,
    };
  }
});

return server;
}

// Create AsyncLocalStorage for request context
const asyncLocalStorage = new AsyncLocalStorage<{
  perplexity_token: string;
}>();

function getPerplexityToken() {
  // First check if env var exists
  if (process.env.PERPLEXITY_API_KEY) {
    return process.env.PERPLEXITY_API_KEY;
  }
  // Fall back to token from request context
  return asyncLocalStorage.getStore()!.perplexity_token;
}

const app = express();

//=============================================================================
// STREAMABLE HTTP TRANSPORT (PROTOCOL VERSION 2025-03-26)
//=============================================================================

app.post('/mcp', async (req: Request, res: Response) => {
  const perplexity_token = req.headers['x-auth-token'] as string;

  if (!perplexity_token) {
    console.error('Error: Perplexity token is missing. Provide it via x-auth-token header.');
  }

    const server = getPerplexityMcpServer();
    try {
        const transport: StreamableHTTPServerTransport = new StreamableHTTPServerTransport({
            sessionIdGenerator: undefined,
        });
        await server.connect(transport);
        asyncLocalStorage.run({ perplexity_token }, async () => {
            await transport.handleRequest(req, res, req.body);
        });
        res.on('close', () => {
            console.log('Request closed');
            transport.close();
            server.close();
        });
    } catch (error) {
        console.error('Error handling MCP request:', error);
        if (!res.headersSent) {
            res.status(500).json({
                jsonrpc: '2.0',
                error: {
                    code: -32603,
                    message: 'Internal server error',
                },
                id: null,
            });
        }
    }
});

app.get('/mcp', async (req: Request, res: Response) => {
    console.log('Received GET MCP request');
    res.writeHead(405).end(JSON.stringify({
        jsonrpc: "2.0",
        error: {
            code: -32000,
            message: "Method not allowed."
        },
        id: null
    }));
});

app.delete('/mcp', async (req: Request, res: Response) => {
    console.log('Received DELETE MCP request');
    res.writeHead(405).end(JSON.stringify({
        jsonrpc: "2.0",
        error: {
            code: -32000,
            message: "Method not allowed."
        },
        id: null
    }));
});

//=============================================================================
// DEPRECATED HTTP+SSE TRANSPORT (PROTOCOL VERSION 2024-11-05)
//=============================================================================
const transports = new Map<string, SSEServerTransport>();

app.get("/sse", async (req, res) => {
  const transport = new SSEServerTransport(`/messages`, res);

  // Set up cleanup when connection closes
  res.on('close', async () => {
    console.log(`SSE connection closed for transport: ${transport.sessionId}`);
    try {
      transports.delete(transport.sessionId);
    } finally {
    }
  });

  transports.set(transport.sessionId, transport);

  const server = getPerplexityMcpServer();
  await server.connect(transport);

  console.log(`SSE connection established with transport: ${transport.sessionId}`);
});

app.post("/messages", async (req, res) => {
  const sessionId = req.query.sessionId as string;

  let transport: SSEServerTransport | undefined;
  transport = sessionId ? transports.get(sessionId) : undefined;
  if (transport) {
    const perplexity_token = req.headers['x-auth-token'] as string;

    if (!perplexity_token) {
      console.error('Error: Perplexity token is missing. Provide it via x-auth-token header.');
    }

    asyncLocalStorage.run({ perplexity_token }, async () => {
      await transport.handlePostMessage(req, res);
    });
  } else {
    console.error(`Transport not found for session ID: ${sessionId}`);
    res.status(404).send({ error: "Transport not found" });
  }
});

app.listen(5000, () => {
  console.log('Perplexity MCP server running on port 5000');
});
