import { describe, it, expect } from 'vitest';

// Helper to call MCP tools via HTTP (assumes server running locally)
async function callTool(tool, args) {
  const res = await fetch('http://localhost:3000/mcp/tool', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: tool, arguments: args })
  });
  return res.json();
}

// Replace with your actual fit-pulse projectId
const fitPulseProjectId = process.env.FIT_PULSE_PROJECT_ID;

describe('Vercel MCP Server Production Integration', () => {
  it('list_projects', async () => {
    const result = await callTool('list_projects', { search: 'fit-pulse', limit: 5 });
    expect(result).toHaveProperty('content');
  });

  it('get_project', async () => {
    const result = await callTool('get_project', { projectId: fitPulseProjectId });
    expect(result).toHaveProperty('content');
  });

  it('list_deployments', async () => {
    const result = await callTool('list_deployments', { projectId: fitPulseProjectId, limit: 5 });
    expect(result).toHaveProperty('content');
  });

  it('get_deployment', async () => {
    // You may need to provide a valid deploymentId
    const deployments = await callTool('list_deployments', { projectId: fitPulseProjectId, limit: 1 });
    const deploymentId = deployments?.content?.[0]?.text?.match(/ID: (\w+)/)?.[1];
    if (deploymentId) {
      const result = await callTool('get_deployment', { deploymentId });
      expect(result).toHaveProperty('content');
    }
  });

  it('get_deployment_logs', async () => {
    // You may need to provide a valid deploymentId
    const deployments = await callTool('list_deployments', { projectId: fitPulseProjectId, limit: 1 });
    const deploymentId = deployments?.content?.[0]?.text?.match(/ID: (\w+)/)?.[1];
    if (deploymentId) {
      const result = await callTool('get_deployment_logs', { deploymentId });
      expect(result).toHaveProperty('content');
    }
  });

  it('list_domains', async () => {
    const result = await callTool('list_domains', { limit: 5 });
    expect(result).toHaveProperty('content');
  });

  it('list_env_vars', async () => {
    const result = await callTool('list_env_vars', { projectId: fitPulseProjectId });
    expect(result).toHaveProperty('content');
  });

  // Add more tests for create/update/delete as needed, using safe test data
});
