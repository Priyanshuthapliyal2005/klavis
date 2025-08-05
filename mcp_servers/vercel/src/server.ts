#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { 
  VercelDeployment, 
  VercelProject, 
  VercelDomain, 
  VercelEnvironmentVariable,
  CreateDeploymentRequest,
  CreateProjectRequest,
  UpdateProjectRequest,
  DeploymentLog
} from './types/vercel.js';
import {
  validateInput,
  ListDeploymentsSchema,
  GetDeploymentSchema,
  CreateDeploymentSchema,
  CancelDeploymentSchema,
  GetDeploymentLogsSchema,
  ListProjectsSchema,
  GetProjectSchema,
  CreateProjectSchema,
  UpdateProjectSchema,
  DeleteProjectSchema,
  ListDomainsSchema,
  AddDomainSchema,
  VerifyDomainSchema,
  RemoveDomainSchema,
  ListEnvVarsSchema,
  CreateEnvVarSchema,
  UpdateEnvVarSchema,
  DeleteEnvVarSchema
} from './mcp.js';
import {
  formatDeployment,
  formatProject,
  formatDomain,
  formatEnvVar,
  sanitizeErrorMessage
} from './util.js';

class VercelMCPServer {
  private server: Server;
  private config: {
    apiToken: string;
    teamId?: string;
    baseUrl: string;
  };

  constructor() {
    this.server = new Server(
      {
        name: 'vercel-mcp-server',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    // Validate and set configuration
    const apiToken = process.env.VERCEL_API_TOKEN;
    if (!apiToken) {
      throw new Error('VERCEL_API_TOKEN environment variable is required');
    }

    this.config = {
      apiToken,
      teamId: process.env.VERCEL_TEAM_ID,
      baseUrl: 'https://api.vercel.com'
    };

    this.setupToolHandlers();
  }

  private setupToolHandlers() {
    // List tools handler
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        // Deployment tools
        {
          name: 'list_deployments',
          description: 'List deployments with optional filtering by project, state, and time range',
          inputSchema: {
            type: 'object',
            properties: {
              projectId: { type: 'string', description: 'Filter by project ID' },
              state: { 
                type: 'string', 
                enum: ['BUILDING', 'ERROR', 'INITIALIZING', 'QUEUED', 'READY', 'CANCELED'],
                description: 'Filter by deployment state' 
              },
              limit: { type: 'number', minimum: 1, maximum: 100, default: 20, description: 'Number of deployments to return' },
              until: { type: 'number', description: 'List deployments created before this timestamp' },
              since: { type: 'number', description: 'List deployments created after this timestamp' }
            }
          }
        },
        {
          name: 'get_deployment',
          description: 'Get detailed information about a specific deployment',
          inputSchema: {
            type: 'object',
            properties: {
              deploymentId: { type: 'string', description: 'The deployment ID or URL' }
            },
            required: ['deploymentId']
          }
        },
        {
          name: 'create_deployment',
          description: 'Create a new deployment from a Git repository',
          inputSchema: {
            type: 'object',
            properties: {
              name: { type: 'string', description: 'Project name for the deployment' },
              gitSource: {
                type: 'object',
                properties: {
                  type: { type: 'string', enum: ['github', 'gitlab', 'bitbucket'] },
                  repo: { type: 'string', description: 'Repository in format owner/repo' },
                  ref: { type: 'string', description: 'Git branch, tag, or commit SHA' }
                }
              },
              target: { type: 'string', enum: ['production', 'staging'], description: 'Deployment target' },
              projectSettings: {
                type: 'object',
                properties: {
                  buildCommand: { type: 'string' },
                  devCommand: { type: 'string' },
                  installCommand: { type: 'string' },
                  outputDirectory: { type: 'string' },
                  rootDirectory: { type: 'string' },
                  framework: { type: 'string' }
                }
              },
              env: { type: 'object', description: 'Environment variables for the deployment' },
              meta: { type: 'object', description: 'Metadata for the deployment' }
            },
            required: ['name']
          }
        },
        {
          name: 'cancel_deployment',
          description: 'Cancel an in-progress deployment',
          inputSchema: {
            type: 'object',
            properties: {
              deploymentId: { type: 'string', description: 'The deployment ID to cancel' }
            },
            required: ['deploymentId']
          }
        },
        {
          name: 'get_deployment_logs',
          description: 'Retrieve build and function logs for a deployment',
          inputSchema: {
            type: 'object',
            properties: {
              deploymentId: { type: 'string', description: 'The deployment ID' },
              follow: { type: 'boolean', default: false, description: 'Follow logs in real-time' },
              since: { type: 'number', description: 'Get logs since this timestamp' },
              until: { type: 'number', description: 'Get logs until this timestamp' }
            },
            required: ['deploymentId']
          }
        },

        // Project management tools
        {
          name: 'list_projects',
          description: 'List all accessible projects',
          inputSchema: {
            type: 'object',
            properties: {
              limit: { type: 'number', minimum: 1, maximum: 100, default: 20, description: 'Number of projects to return' },
              from: { type: 'string', description: 'Pagination cursor' },
              search: { type: 'string', description: 'Search projects by name' }
            }
          }
        },
        {
          name: 'get_project',
          description: 'Get detailed information about a specific project',
          inputSchema: {
            type: 'object',
            properties: {
              projectId: { type: 'string', description: 'The project ID or name' }
            },
            required: ['projectId']
          }
        },
        {
          name: 'create_project',
          description: 'Create a new project from a Git repository',
          inputSchema: {
            type: 'object',
            properties: {
              name: { type: 'string', description: 'Project name' },
              gitRepository: {
                type: 'object',
                properties: {
                  type: { type: 'string', enum: ['github', 'gitlab', 'bitbucket'] },
                  repo: { type: 'string', description: 'Repository in format owner/repo' }
                }
              },
              buildCommand: { type: 'string' },
              devCommand: { type: 'string' },
              framework: { type: 'string' },
              installCommand: { type: 'string' },
              outputDirectory: { type: 'string' },
              publicSource: { type: 'boolean' },
              rootDirectory: { type: 'string' },
              serverlessFunctionRegion: { type: 'string' },
              environmentVariables: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    key: { type: 'string' },
                    value: { type: 'string' },
                    target: {
                      type: 'array',
                      items: { type: 'string', enum: ['production', 'preview', 'development'] }
                    }
                  },
                  required: ['key', 'value', 'target']
                }
              }
            },
            required: ['name']
          }
        },
        {
          name: 'update_project',
          description: 'Update project configuration and settings',
          inputSchema: {
            type: 'object',
            properties: {
              projectId: { type: 'string', description: 'The project ID' },
              name: { type: 'string' },
              buildCommand: { type: 'string' },
              devCommand: { type: 'string' },
              framework: { type: 'string' },
              installCommand: { type: 'string' },
              outputDirectory: { type: 'string' },
              publicSource: { type: 'boolean' },
              rootDirectory: { type: 'string' },
              serverlessFunctionRegion: { type: 'string' }
            },
            required: ['projectId']
          }
        },
        {
          name: 'delete_project',
          description: 'Delete a project (WARNING: This action cannot be undone)',
          inputSchema: {
            type: 'object',
            properties: {
              projectId: { type: 'string', description: 'The project ID to delete' }
            },
            required: ['projectId']
          }
        },

        // Domain management tools
        {
          name: 'list_domains',
          description: 'List all configured custom domains',
          inputSchema: {
            type: 'object',
            properties: {
              limit: { type: 'number', minimum: 1, maximum: 100, default: 20 },
              since: { type: 'number', description: 'List domains created after this timestamp' },
              until: { type: 'number', description: 'List domains created before this timestamp' }
            }
          }
        },
        {
          name: 'add_domain',
          description: 'Add a custom domain to a project',
          inputSchema: {
            type: 'object',
            properties: {
              name: { type: 'string', description: 'Domain name (e.g., example.com)' },
              projectId: { type: 'string', description: 'Project ID to add domain to' },
              redirect: { type: 'string', description: 'Redirect URL' },
              redirectStatusCode: { type: 'number', description: 'HTTP status code for redirect' },
              gitBranch: { type: 'string', description: 'Git branch for this domain' }
            },
            required: ['name', 'projectId']
          }
        },
        {
          name: 'verify_domain',
          description: 'Check domain verification status and get verification records',
          inputSchema: {
            type: 'object',
            properties: {
              domainName: { type: 'string', description: 'Domain name to verify' }
            },
            required: ['domainName']
          }
        },
        {
          name: 'remove_domain',
          description: 'Remove a custom domain from the account',
          inputSchema: {
            type: 'object',
            properties: {
              domainName: { type: 'string', description: 'Domain name to remove' }
            },
            required: ['domainName']
          }
        },

        // Environment variables tools
        {
          name: 'list_env_vars',
          description: 'List environment variables for a project',
          inputSchema: {
            type: 'object',
            properties: {
              projectId: { type: 'string', description: 'Project ID' },
              decrypt: { type: 'boolean', default: false, description: 'Decrypt sensitive values' }
            },
            required: ['projectId']
          }
        },
        {
          name: 'create_env_var',
          description: 'Add a new environment variable to a project',
          inputSchema: {
            type: 'object',
            properties: {
              projectId: { type: 'string', description: 'Project ID' },
              key: { type: 'string', description: 'Environment variable name' },
              value: { type: 'string', description: 'Environment variable value' },
              target: {
                type: 'array',
                items: { type: 'string', enum: ['production', 'preview', 'development'] },
                description: 'Target environments'
              },
              gitBranch: { type: 'string', description: 'Specific git branch' },
              type: { 
                type: 'string', 
                enum: ['system', 'secret', 'encrypted', 'plain'], 
                default: 'encrypted',
                description: 'Variable type'
              }
            },
            required: ['projectId', 'key', 'value', 'target']
          }
        },
        {
          name: 'update_env_var',
          description: 'Update an existing environment variable',
          inputSchema: {
            type: 'object',
            properties: {
              projectId: { type: 'string', description: 'Project ID' },
              envVarId: { type: 'string', description: 'Environment variable ID' },
              key: { type: 'string', description: 'New variable name' },
              value: { type: 'string', description: 'New variable value' },
              target: {
                type: 'array',
                items: { type: 'string', enum: ['production', 'preview', 'development'] },
                description: 'Target environments'
              },
              gitBranch: { type: 'string', description: 'Specific git branch' },
              type: { 
                type: 'string', 
                enum: ['system', 'secret', 'encrypted', 'plain'], 
                description: 'Variable type'
              }
            },
            required: ['projectId', 'envVarId']
          }
        },
        {
          name: 'delete_env_var',
          description: 'Delete an environment variable from a project',
          inputSchema: {
            type: 'object',
            properties: {
              projectId: { type: 'string', description: 'Project ID' },
              envVarId: { type: 'string', description: 'Environment variable ID to delete' }
            },
            required: ['projectId', 'envVarId']
          }
        }
      ]
    }));

    // Call tool handler
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      try {
        switch (request.params.name) {
          // Deployment tools
          case 'list_deployments':
            return await this.listDeployments(request.params.arguments);
          case 'get_deployment':
            return await this.getDeployment(request.params.arguments);
          case 'create_deployment':
            return await this.createDeployment(request.params.arguments);
          case 'cancel_deployment':
            return await this.cancelDeployment(request.params.arguments);
          case 'get_deployment_logs':
            return await this.getDeploymentLogs(request.params.arguments);

          // Project management tools
          case 'list_projects':
            return await this.listProjects(request.params.arguments);
          case 'get_project':
            return await this.getProject(request.params.arguments);
          case 'create_project':
            return await this.createProject(request.params.arguments);
          case 'update_project':
            return await this.updateProject(request.params.arguments);
          case 'delete_project':
            return await this.deleteProject(request.params.arguments);

          // Domain management tools
          case 'list_domains':
            return await this.listDomains(request.params.arguments);
          case 'add_domain':
            return await this.addDomain(request.params.arguments);
          case 'verify_domain':
            return await this.verifyDomain(request.params.arguments);
          case 'remove_domain':
            return await this.removeDomain(request.params.arguments);

          // Environment variables tools
          case 'list_env_vars':
            return await this.listEnvVars(request.params.arguments);
          case 'create_env_var':
            return await this.createEnvVar(request.params.arguments);
          case 'update_env_var':
            return await this.updateEnvVar(request.params.arguments);
          case 'delete_env_var':
            return await this.deleteEnvVar(request.params.arguments);

          default:
            throw new Error(`Unknown tool: ${request.params.name}`);
        }
      } catch (error) {
        return {
          content: [
            {
              type: 'text',
              text: `Error: ${sanitizeErrorMessage(error)}`
            }
          ]
        };
      }
    });
  }

  private async makeRequest<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.config.baseUrl}${endpoint}`;
    const headers = {
      'Authorization': `Bearer ${this.config.apiToken}`,
      'Content-Type': 'application/json',
      ...options.headers
    };

    // Add team ID to query params if configured
    const urlObj = new URL(url);
    if (this.config.teamId) {
      urlObj.searchParams.set('teamId', this.config.teamId);
    }

    const response = await fetch(urlObj.toString(), {
      ...options,
      headers
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      
      try {
        const errorData = JSON.parse(errorText);
        if (errorData.error?.message) {
          errorMessage = errorData.error.message;
        }
      } catch {
        // Use HTTP status message if JSON parsing fails
      }
      
      throw new Error(errorMessage);
    }

    const data = await response.json();
    return data as T;
  }

  // Deployment tools implementation
  private async listDeployments(args: any) {
    const validatedArgs = validateInput(ListDeploymentsSchema, args || {});
    
    const queryParams = new URLSearchParams();
    if (validatedArgs.projectId) queryParams.set('projectId', validatedArgs.projectId);
    if (validatedArgs.state) queryParams.set('state', validatedArgs.state);
    if (validatedArgs.limit) queryParams.set('limit', validatedArgs.limit.toString());
    if (validatedArgs.until) queryParams.set('until', validatedArgs.until.toString());
    if (validatedArgs.since) queryParams.set('since', validatedArgs.since.toString());

    const endpoint = `/v6/deployments?${queryParams.toString()}`;
    const response = await this.makeRequest<{ deployments: VercelDeployment[] }>(endpoint);

    const formattedDeployments = response.deployments
      .map(deployment => formatDeployment(deployment))
      .join('\n');

    return {
      content: [
        {
          type: 'text',
          text: `Found ${response.deployments.length} deployments:\n\n${formattedDeployments}`
        }
      ]
    };
  }

  private async getDeployment(args: any) {
    const validatedArgs = validateInput(GetDeploymentSchema, args);
    
    const endpoint = `/v13/deployments/${validatedArgs.deploymentId}`;
    const deployment = await this.makeRequest<VercelDeployment>(endpoint);

    const details = [
      `🚀 Deployment Details`,
      ``,
      `ID: ${deployment.uid}`,
      `Name: ${deployment.name}`,
      `URL: ${deployment.url}`,
      `State: ${deployment.state}`,
      `Created: ${new Date(deployment.created).toISOString()}`,
      `Project ID: ${deployment.projectId || 'N/A'}`,
      `Target: ${deployment.target || 'N/A'}`,
      `Type: ${deployment.type || 'N/A'}`
    ];

    if (deployment.gitSource) {
      details.push(`Git Source: ${deployment.gitSource.type}:${deployment.gitSource.repo}@${deployment.gitSource.ref || 'main'}`);
    }

    if (deployment.alias && deployment.alias.length > 0) {
      details.push(`Aliases: ${deployment.alias.join(', ')}`);
    }

    return {
      content: [
        {
          type: 'text',
          text: details.join('\n')
        }
      ]
    };
  }

  private async createDeployment(args: any) {
    const validatedArgs = validateInput(CreateDeploymentSchema, args);

    const deploymentData: CreateDeploymentRequest = {
      name: validatedArgs.name,
      ...(validatedArgs.gitSource && { gitSource: validatedArgs.gitSource }),
      ...(validatedArgs.target && { target: validatedArgs.target }),
      ...(validatedArgs.projectSettings && { projectSettings: validatedArgs.projectSettings }),
      ...(validatedArgs.env && { env: validatedArgs.env }),
      ...(validatedArgs.meta && { meta: validatedArgs.meta })
    };

    const endpoint = '/v13/deployments';
    const deployment = await this.makeRequest<VercelDeployment>(endpoint, {
      method: 'POST',
      body: JSON.stringify(deploymentData)
    });

    return {
      content: [
        {
          type: 'text',
          text: `✅ Deployment created successfully!\n\n${formatDeployment(deployment)}\n\nYou can monitor the deployment at: ${deployment.url}`
        }
      ]
    };
  }

  private async cancelDeployment(args: any) {
    const validatedArgs = validateInput(CancelDeploymentSchema, args);
    
    const endpoint = `/v12/deployments/${validatedArgs.deploymentId}`;
    await this.makeRequest(endpoint, { method: 'DELETE' });

    return {
      content: [
        {
          type: 'text',
          text: `✅ Deployment ${validatedArgs.deploymentId} has been canceled.`
        }
      ]
    };
  }

  private async getDeploymentLogs(args: any) {
    const validatedArgs = validateInput(GetDeploymentLogsSchema, args);
    
    const queryParams = new URLSearchParams();
    if (validatedArgs.follow) queryParams.set('follow', 'true');
    if (validatedArgs.since) queryParams.set('since', validatedArgs.since.toString());
    if (validatedArgs.until) queryParams.set('until', validatedArgs.until.toString());

    const endpoint = `/v2/deployments/${validatedArgs.deploymentId}/events?${queryParams.toString()}`;
    const response = await this.makeRequest<DeploymentLog>(endpoint);

    const formattedLogs = response.data
      .map(log => `[${new Date(log.timestamp).toISOString()}] ${log.type.toUpperCase()}: ${log.message}`)
      .join('\n');

    return {
      content: [
        {
          type: 'text',
          text: `📋 Deployment Logs:\n\n${formattedLogs || 'No logs available'}`
        }
      ]
    };
  }

  // Project management tools implementation
  private async listProjects(args: any) {
    const validatedArgs = validateInput(ListProjectsSchema, args || {});
    
    const queryParams = new URLSearchParams();
    if (validatedArgs.limit) queryParams.set('limit', validatedArgs.limit.toString());
    if (validatedArgs.from) queryParams.set('from', validatedArgs.from);
    if (validatedArgs.search) queryParams.set('search', validatedArgs.search);

    const endpoint = `/v9/projects?${queryParams.toString()}`;
    const response = await this.makeRequest<{ projects: VercelProject[] }>(endpoint);

    const formattedProjects = response.projects
      .map(project => formatProject(project))
      .join('\n');

    return {
      content: [
        {
          type: 'text',
          text: `Found ${response.projects.length} projects:\n\n${formattedProjects}`
        }
      ]
    };
  }

  private async getProject(args: any) {
    const validatedArgs = validateInput(GetProjectSchema, args);
    
    const endpoint = `/v9/projects/${validatedArgs.projectId}`;
    const project = await this.makeRequest<VercelProject>(endpoint);

    const details = [
      `📁 Project Details`,
      ``,
      `ID: ${project.id}`,
      `Name: ${project.name}`,
      `Framework: ${project.framework || 'N/A'}`,
      `Created: ${new Date(project.createdAt).toISOString()}`,
      `Updated: ${project.updatedAt ? new Date(project.updatedAt).toISOString() : 'N/A'}`,
      `Build Command: ${project.buildCommand || 'N/A'}`,
      `Dev Command: ${project.devCommand || 'N/A'}`,
      `Install Command: ${project.installCommand || 'N/A'}`,
      `Output Directory: ${project.outputDirectory || 'N/A'}`,
      `Root Directory: ${project.rootDirectory || 'N/A'}`,
      `Public Source: ${project.publicSource ? 'Yes' : 'No'}`
    ];

    if (project.gitRepository) {
      details.push(`Git Repository: ${project.gitRepository.type}:${project.gitRepository.repo}`);
    }

    return {
      content: [
        {
          type: 'text',
          text: details.join('\n')
        }
      ]
    };
  }

  private async createProject(args: any) {
    const validatedArgs = validateInput(CreateProjectSchema, args);

    const projectData: CreateProjectRequest = {
      name: validatedArgs.name,
      ...(validatedArgs.gitRepository && { gitRepository: validatedArgs.gitRepository }),
      ...(validatedArgs.buildCommand && { buildCommand: validatedArgs.buildCommand }),
      ...(validatedArgs.devCommand && { devCommand: validatedArgs.devCommand }),
      ...(validatedArgs.framework && { framework: validatedArgs.framework }),
      ...(validatedArgs.installCommand && { installCommand: validatedArgs.installCommand }),
      ...(validatedArgs.outputDirectory && { outputDirectory: validatedArgs.outputDirectory }),
      ...(validatedArgs.publicSource !== undefined && { publicSource: validatedArgs.publicSource }),
      ...(validatedArgs.rootDirectory && { rootDirectory: validatedArgs.rootDirectory }),
      ...(validatedArgs.serverlessFunctionRegion && { serverlessFunctionRegion: validatedArgs.serverlessFunctionRegion }),
      ...(validatedArgs.environmentVariables && { environmentVariables: validatedArgs.environmentVariables })
    };

    const endpoint = '/v10/projects';
    const project = await this.makeRequest<VercelProject>(endpoint, {
      method: 'POST',
      body: JSON.stringify(projectData)
    });

    return {
      content: [
        {
          type: 'text',
          text: `✅ Project created successfully!\n\n${formatProject(project)}`
        }
      ]
    };
  }

  private async updateProject(args: any) {
    const validatedArgs = validateInput(UpdateProjectSchema, args);

    const updateData: UpdateProjectRequest = {};
    if (validatedArgs.name) updateData.name = validatedArgs.name;
    if (validatedArgs.buildCommand) updateData.buildCommand = validatedArgs.buildCommand;
    if (validatedArgs.devCommand) updateData.devCommand = validatedArgs.devCommand;
    if (validatedArgs.framework) updateData.framework = validatedArgs.framework;
    if (validatedArgs.installCommand) updateData.installCommand = validatedArgs.installCommand;
    if (validatedArgs.outputDirectory) updateData.outputDirectory = validatedArgs.outputDirectory;
    if (validatedArgs.publicSource !== undefined) updateData.publicSource = validatedArgs.publicSource;
    if (validatedArgs.rootDirectory) updateData.rootDirectory = validatedArgs.rootDirectory;
    if (validatedArgs.serverlessFunctionRegion) updateData.serverlessFunctionRegion = validatedArgs.serverlessFunctionRegion;

    const endpoint = `/v9/projects/${validatedArgs.projectId}`;
    const project = await this.makeRequest<VercelProject>(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(updateData)
    });

    return {
      content: [
        {
          type: 'text',
          text: `✅ Project updated successfully!\n\n${formatProject(project)}`
        }
      ]
    };
  }

  private async deleteProject(args: any) {
    const validatedArgs = validateInput(DeleteProjectSchema, args);
    
    const endpoint = `/v9/projects/${validatedArgs.projectId}`;
    await this.makeRequest(endpoint, { method: 'DELETE' });

    return {
      content: [
        {
          type: 'text',
          text: `✅ Project ${validatedArgs.projectId} has been deleted permanently.`
        }
      ]
    };
  }

  // Domain management tools implementation
  private async listDomains(args: any) {
    const validatedArgs = validateInput(ListDomainsSchema, args || {});
    
    const queryParams = new URLSearchParams();
    if (validatedArgs.limit) queryParams.set('limit', validatedArgs.limit.toString());
    if (validatedArgs.since) queryParams.set('since', validatedArgs.since.toString());
    if (validatedArgs.until) queryParams.set('until', validatedArgs.until.toString());

    const endpoint = `/v4/domains?${queryParams.toString()}`;
    const response = await this.makeRequest<{ domains: VercelDomain[] }>(endpoint);

    const formattedDomains = response.domains
      .map(domain => formatDomain(domain))
      .join('\n');

    return {
      content: [
        {
          type: 'text',
          text: `Found ${response.domains.length} domains:\n\n${formattedDomains}`
        }
      ]
    };
  }

  private async addDomain(args: any) {
    const validatedArgs = validateInput(AddDomainSchema, args);

    const domainData = {
      name: validatedArgs.name,
      projectId: validatedArgs.projectId,
      ...(validatedArgs.redirect && { redirect: validatedArgs.redirect }),
      ...(validatedArgs.redirectStatusCode && { redirectStatusCode: validatedArgs.redirectStatusCode }),
      ...(validatedArgs.gitBranch && { gitBranch: validatedArgs.gitBranch })
    };

    const endpoint = '/v5/domains';
    const domain = await this.makeRequest<VercelDomain>(endpoint, {
      method: 'POST',
      body: JSON.stringify(domainData)
    });

    return {
      content: [
        {
          type: 'text',
          text: `✅ Domain added successfully!\n\n${formatDomain(domain)}\n\nVerification may be required. Use verify_domain to check status.`
        }
      ]
    };
  }

  private async verifyDomain(args: any) {
    const validatedArgs = validateInput(VerifyDomainSchema, args);
    
    const endpoint = `/v6/domains/${validatedArgs.domainName}/verify`;
    const response = await this.makeRequest<VercelDomain>(endpoint, { method: 'POST' });

    const verificationDetails = response.verification
      ?.map(v => `  ${v.type}: ${v.value} (${v.reason})`)
      .join('\n') || 'No verification records';

    return {
      content: [
        {
          type: 'text',
          text: `🔍 Domain Verification Status:\n\nDomain: ${response.name}\nVerified: ${response.verified ? '✅ Yes' : '❌ No'}\n\nVerification Records:\n${verificationDetails}`
        }
      ]
    };
  }

  private async removeDomain(args: any) {
    const validatedArgs = validateInput(RemoveDomainSchema, args);
    
    const endpoint = `/v6/domains/${validatedArgs.domainName}`;
    await this.makeRequest(endpoint, { method: 'DELETE' });

    return {
      content: [
        {
          type: 'text',
          text: `✅ Domain ${validatedArgs.domainName} has been removed.`
        }
      ]
    };
  }

  // Environment variables tools implementation
  private async listEnvVars(args: any) {
    const validatedArgs = validateInput(ListEnvVarsSchema, args);
    
    const queryParams = new URLSearchParams();
    if (validatedArgs.decrypt) queryParams.set('decrypt', 'true');

    const endpoint = `/v8/projects/${validatedArgs.projectId}/env?${queryParams.toString()}`;
    const response = await this.makeRequest<{ envs: VercelEnvironmentVariable[] }>(endpoint);

    const formattedEnvVars = response.envs
      .map(envVar => formatEnvVar(envVar))
      .join('\n');

    return {
      content: [
        {
          type: 'text',
          text: `Found ${response.envs.length} environment variables:\n\n${formattedEnvVars}`
        }
      ]
    };
  }

  private async createEnvVar(args: any) {
    const validatedArgs = validateInput(CreateEnvVarSchema, args);

    const envVarData = {
      key: validatedArgs.key,
      value: validatedArgs.value,
      target: validatedArgs.target,
      type: validatedArgs.type || 'encrypted',
      ...(validatedArgs.gitBranch && { gitBranch: validatedArgs.gitBranch })
    };

    const endpoint = `/v10/projects/${validatedArgs.projectId}/env`;
    const envVar = await this.makeRequest<VercelEnvironmentVariable>(endpoint, {
      method: 'POST',
      body: JSON.stringify(envVarData)
    });

    return {
      content: [
        {
          type: 'text',
          text: `✅ Environment variable created successfully!\n\n${formatEnvVar(envVar)}`
        }
      ]
    };
  }

  private async updateEnvVar(args: any) {
    const validatedArgs = validateInput(UpdateEnvVarSchema, args);

    const updateData: any = {};
    if (validatedArgs.key) updateData.key = validatedArgs.key;
    if (validatedArgs.value) updateData.value = validatedArgs.value;
    if (validatedArgs.target) updateData.target = validatedArgs.target;
    if (validatedArgs.type) updateData.type = validatedArgs.type;
    if (validatedArgs.gitBranch) updateData.gitBranch = validatedArgs.gitBranch;

    const endpoint = `/v9/projects/${validatedArgs.projectId}/env/${validatedArgs.envVarId}`;
    const envVar = await this.makeRequest<VercelEnvironmentVariable>(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(updateData)
    });

    return {
      content: [
        {
          type: 'text',
          text: `✅ Environment variable updated successfully!\n\n${formatEnvVar(envVar)}`
        }
      ]
    };
  }

  private async deleteEnvVar(args: any) {
    const validatedArgs = validateInput(DeleteEnvVarSchema, args);
    
    const endpoint = `/v9/projects/${validatedArgs.projectId}/env/${validatedArgs.envVarId}`;
    await this.makeRequest(endpoint, { method: 'DELETE' });

    return {
      content: [
        {
          type: 'text',
          text: `✅ Environment variable ${validatedArgs.envVarId} has been deleted.`
        }
      ]
    };
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
  }
}

async function main() {
  try {
    const server = new VercelMCPServer();
    await server.run();
  } catch (error) {
    console.error('Failed to start Vercel MCP Server:', error);
    process.exit(1);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(console.error);
}
