import { VercelDeployment, VercelProject, VercelDomain, VercelEnvironmentVariable } from './types/vercel.js';

/**
 * Utility functions for the Vercel MCP Server
 */

/**
 * Format timestamp to human-readable date
 */
export function formatTimestamp(timestamp: number): string {
  return new Date(timestamp).toISOString();
}

/**
 * Get deployment status color for display
 */
export function getDeploymentStatusColor(state: string): string {
  switch (state) {
    case 'READY':
      return '🟢';
    case 'BUILDING':
      return '🟡';
    case 'ERROR':
      return '🔴';
    case 'CANCELED':
      return '⚫';
    case 'QUEUED':
    case 'INITIALIZING':
      return '🔵';
    default:
      return '⚪';
  }
}

/**
 * Format deployment for display
 */
export function formatDeployment(deployment: VercelDeployment): string {
  const status = getDeploymentStatusColor(deployment.state);
  const created = formatTimestamp(deployment.created);
  return `${status} ${deployment.name} (${deployment.state}) - ${deployment.url} - Created: ${created}`;
}

/**
 * Format project for display
 */
export function formatProject(project: VercelProject): string {
  const created = formatTimestamp(project.createdAt);
  const framework = project.framework ? ` [${project.framework}]` : '';
  const repo = project.gitRepository ? ` (${project.gitRepository.repo})` : '';
  return `📁 ${project.name}${framework}${repo} - Created: ${created}`;
}

/**
 * Format domain for display
 */
export function formatDomain(domain: VercelDomain): string {
  const status = domain.verified ? '✅' : '⚠️';
  const created = domain.createdAt ? formatTimestamp(domain.createdAt) : 'Unknown';
  return `${status} ${domain.name} - Verified: ${domain.verified} - Created: ${created}`;
}

/**
 * Format environment variable for display (masked value)
 */
export function formatEnvVar(envVar: VercelEnvironmentVariable): string {
  const targets = envVar.target.join(', ');
  const maskedValue = envVar.type === 'plain' ? envVar.value : '***ENCRYPTED***';
  const created = envVar.createdAt ? formatTimestamp(envVar.createdAt) : 'Unknown';
  return `🔐 ${envVar.key}=${maskedValue} [${targets}] (${envVar.type}) - Created: ${created}`;
}

/**
 * Validate URL format
 */
export function isValidUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * Validate domain name format
 */
export function isValidDomain(domain: string): boolean {
  const domainRegex = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
  return domainRegex.test(domain) && domain.length <= 253;
}

/**
 * Validate environment variable key format
 */
export function isValidEnvVarKey(key: string): boolean {
  const envVarRegex = /^[A-Z_][A-Z0-9_]*$/;
  return envVarRegex.test(key);
}

/**
 * Generate a slug from a name
 */
export function generateSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .substring(0, 63);
}

/**
 * Parse Git repository URL
 */
export function parseGitUrl(url: string): { type: 'github' | 'gitlab' | 'bitbucket'; repo: string } | null {
  // GitHub patterns
  const githubHttpsMatch = url.match(/https:\/\/github\.com\/([^/]+\/[^/]+)/);
  const githubSshMatch = url.match(/git@github\.com:([^/]+\/[^/]+)\.git/);
  
  if (githubHttpsMatch || githubSshMatch) {
    const repo = (githubHttpsMatch?.[1] || githubSshMatch?.[1])?.replace(/\.git$/, '');
    if (repo) return { type: 'github', repo };
  }

  // GitLab patterns
  const gitlabHttpsMatch = url.match(/https:\/\/gitlab\.com\/([^/]+\/[^/]+)/);
  const gitlabSshMatch = url.match(/git@gitlab\.com:([^/]+\/[^/]+)\.git/);
  
  if (gitlabHttpsMatch || gitlabSshMatch) {
    const repo = (gitlabHttpsMatch?.[1] || gitlabSshMatch?.[1])?.replace(/\.git$/, '');
    if (repo) return { type: 'gitlab', repo };
  }

  // Bitbucket patterns
  const bitbucketHttpsMatch = url.match(/https:\/\/bitbucket\.org\/([^/]+\/[^/]+)/);
  const bitbucketSshMatch = url.match(/git@bitbucket\.org:([^/]+\/[^/]+)\.git/);
  
  if (bitbucketHttpsMatch || bitbucketSshMatch) {
    const repo = (bitbucketHttpsMatch?.[1] || bitbucketSshMatch?.[1])?.replace(/\.git$/, '');
    if (repo) return { type: 'bitbucket', repo };
  }

  return null;
}

/**
 * Sanitize error message for display
 */
export function sanitizeErrorMessage(error: any): string {
  if (typeof error === 'string') {
    return error;
  }
  
  if (error?.message) {
    return error.message;
  }
  
  if (error?.error?.message) {
    return error.error.message;
  }
  
  return 'An unknown error occurred';
}

/**
 * Create retry delay with exponential backoff
 */
export function createRetryDelay(attempt: number, baseDelay = 1000, maxDelay = 30000): number {
  const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
  // Add jitter to prevent thundering herd
  return delay + Math.random() * 1000;
}

/**
 * Sleep for specified milliseconds
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Chunk array into smaller arrays
 */
export function chunkArray<T>(array: T[], chunkSize: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < array.length; i += chunkSize) {
    chunks.push(array.slice(i, i + chunkSize));
  }
  return chunks;
}

/**
 * Deep merge objects
 */
export function deepMerge(target: any, source: any): any {
  if (typeof target !== 'object' || target === null) {
    return source;
  }
  
  if (typeof source !== 'object' || source === null) {
    return target;
  }
  
  const result = { ...target };
  
  for (const key in source) {
    if (source.hasOwnProperty(key)) {
      if (typeof source[key] === 'object' && source[key] !== null && !Array.isArray(source[key])) {
        result[key] = deepMerge(target[key], source[key]);
      } else {
        result[key] = source[key];
      }
    }
  }
  
  return result;
}
