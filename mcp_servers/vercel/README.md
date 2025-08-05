# Vercel MCP Server

A Model Context Protocol (MCP) server that provides integration with the Vercel deployment platform. This server enables AI assistants to manage deployments, projects, domains, and environment variables through Vercel's API.

## Features

### 🚀 Deployment Management
- **`list_deployments`** - List deployments with filtering by project, state, and time range
- **`get_deployment`** - Get detailed information about a specific deployment
- **`create_deployment`** - Create new deployments from Git repositories
- **`cancel_deployment`** - Cancel in-progress deployments
- **`get_deployment_logs`** - Retrieve build and function logs

### 📁 Project Management
- **`list_projects`** - List all accessible projects
- **`get_project`** - Get detailed project information and settings
- **`create_project`** - Create new projects from Git repositories
- **`update_project`** - Update project configuration and settings
- **`delete_project`** - Remove projects (with confirmation)

### 🌐 Domain Management
- **`list_domains`** - List all configured custom domains
- **`add_domain`** - Add custom domains to projects
- **`verify_domain`** - Check domain verification status
- **`remove_domain`** - Remove domains from projects

### ⚙️ Environment Variables
- **`list_env_vars`** - List project environment variables
- **`create_env_var`** - Add new environment variables
- **`update_env_var`** - Modify existing environment variables
- **`delete_env_var`** - Remove environment variables

## Prerequisites

- **Node.js:** Version 18 or higher
- **Vercel API Token:** Get from [Vercel Account Settings](https://vercel.com/account/tokens)
- **Docker:** Optional, for containerized deployment

## Installation

### Option 1: Using Docker (Recommended)

1. **Build the Docker image:**
   ```bash
   docker build -t vercel-mcp-server .
   ```

2. **Run the container:**
   ```bash
   docker run -p 3000:3000 --env-file .env vercel-mcp-server
   ```

### Option 2: Local Development

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Build the server:**
   ```bash
   npm run build
   ```

3. **Start the server:**
   ```bash
   npm start
   ```

## Configuration

Create a `.env` file in the root directory:

```env
# Required - Get from https://vercel.com/account/tokens
VERCEL_API_TOKEN=your_vercel_api_token_here

# Optional - For team-based operations
VERCEL_TEAM_ID=your_team_id_here
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VERCEL_API_TOKEN` | Yes | Your Vercel API token for authentication |
| `VERCEL_TEAM_ID` | No | Team ID for team-based operations |

## Usage Examples

### List Recent Deployments
```typescript
// List the 10 most recent deployments
await client.callTool('list_deployments', { limit: 10 });

// List deployments for a specific project
await client.callTool('list_deployments', { 
  projectId: 'prj_abc123',
  state: 'READY'
});
```

### Create a New Deployment
```typescript
await client.callTool('create_deployment', {
  name: 'my-awesome-app',
  gitSource: {
    type: 'github',
    repo: 'username/my-repo',
    ref: 'main'
  },
  target: 'production'
});
```

### Manage Environment Variables
```typescript
// Add a new environment variable
await client.callTool('create_env_var', {
  projectId: 'prj_abc123',
  key: 'DATABASE_URL',
  value: 'postgresql://...',
  target: ['production', 'preview']
});

// List all environment variables
await client.callTool('list_env_vars', {
  projectId: 'prj_abc123'
});
```

### Domain Management
```typescript
// Add a custom domain
await client.callTool('add_domain', {
  name: 'mydomain.com',
  projectId: 'prj_abc123'
});

// Verify domain status
await client.callTool('verify_domain', {
  domainName: 'mydomain.com'
});
```

## API Integration

This server integrates with the following Vercel API endpoints:

- **Deployments:** `/v6/deployments`, `/v13/deployments`, `/v12/deployments`
- **Projects:** `/v9/projects`, `/v10/projects`
- **Domains:** `/v4/domains`, `/v5/domains`, `/v6/domains`
- **Environment Variables:** `/v8/projects/{id}/env`, `/v9/projects/{id}/env`, `/v10/projects/{id}/env`

## Development

### Running Tests
```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run E2E tests
npm run test:e2e
```

### Code Quality
```bash
# Lint code
npm run lint

# Build for production
npm run build

# Development with hot reload
npm run dev
```

### Project Structure
```
src/
├── types/
│   └── vercel.ts          # TypeScript type definitions
├── server.ts              # Main MCP server implementation
├── mcp.ts                 # MCP-specific utilities and schemas
└── util.ts                # Helper functions and formatters

test/
├── server.test.ts         # Unit tests
├── mocks.ts               # Test mocks and fixtures
├── extensions.ts          # Test extensions
└── extensions.d.ts        # Test type extensions
```

## Error Handling

The server includes comprehensive error handling for:

- **Authentication errors** - Invalid API tokens
- **Rate limiting** - Automatic retry with exponential backoff
- **Network errors** - Connection timeouts and failures
- **Validation errors** - Invalid input parameters
- **API errors** - Vercel API error responses

## Security Considerations

- **API Token Security:** Store your Vercel API token securely
- **Team Access:** Use team-scoped tokens when working with team projects
- **Environment Variables:** Never commit sensitive data to version control
- **Network Security:** Use HTTPS for all API communications

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `npm test`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation:** [Vercel API Documentation](https://vercel.com/docs/rest-api)
- **Issues:** [GitHub Issues](https://github.com/klavis-ai/klavis/issues)
- **Discord:** [Klavis AI Community](https://discord.gg/klavis-ai)

## Changelog

### v1.0.0
- Initial release with full Vercel API integration
- Support for deployments, projects, domains, and environment variables
- Comprehensive error handling and validation
- Docker support for easy deployment
- Complete test suite with 90%+ coverage
