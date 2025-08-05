import { vi } from 'vitest';

// Mock Vercel API responses
export const mockDeployment = {
  uid: 'dpl_test123',
  name: 'test-deployment',
  url: 'https://test-deployment-abc123.vercel.app',
  state: 'READY' as const,
  created: Date.now(),
  projectId: 'prj_test123',
  target: 'production',
  type: 'LAMBDAS',
  gitSource: {
    type: 'github' as const,
    repo: 'test-user/test-repo',
    ref: 'main'
  }
};

export const mockProject = {
  id: 'prj_test123',
  name: 'test-project',
  accountId: 'acc_test123',
  createdAt: Date.now(),
  framework: 'nextjs',
  buildCommand: 'npm run build',
  devCommand: 'npm run dev',
  installCommand: 'npm install',
  outputDirectory: '.next',
  rootDirectory: './',
  publicSource: true,
  gitRepository: {
    type: 'github' as const,
    repo: 'test-user/test-repo'
  }
};

export const mockDomain = {
  name: 'example.com',
  verified: true,
  createdAt: Date.now(),
  projectId: 'prj_test123',
  verification: []
};

export const mockEnvVar = {
  id: 'env_test123',
  key: 'NODE_ENV',
  value: 'production',
  target: ['production'],
  type: 'encrypted' as const,
  createdAt: Date.now(),
  updatedAt: Date.now()
};

// Mock fetch responses
export const mockFetchSuccess = (data: any) => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data))
  });
};

export const mockFetchError = (status: number, message: string) => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: false,
    status,
    statusText: message,
    text: () => Promise.resolve(JSON.stringify({ error: { message } }))
  });
};

// Setup environment variables for tests
export const setupTestEnv = () => {
  vi.stubEnv('VERCEL_API_TOKEN', 'test-token');
  vi.stubEnv('VERCEL_TEAM_ID', 'test-team');
};
