import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import fastify, { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import cors from '@fastify/cors';
import dotenv from 'dotenv';

dotenv.config();

export interface MCPTool {
    name: string;
    description: string;
    inputSchema: any;
}

export abstract class BaseMCPServer {
    protected server: Server;
    protected app: FastifyInstance;
    protected port: number;
    protected host: string;
    protected serviceName: string;

    constructor(serviceName: string, port: number, host: string = "0.0.0.0") {
        this.serviceName = serviceName;
        this.port = port;
        this.host = host;

        this.server = new Server({
            name: serviceName,
            version: '1.0.0',
        }, {
            capabilities: {
                tools: {},
            },
        });

        this.app = fastify({
            logger: {
                level: process.env.NODE_ENV === 'production' ? 'info' : 'debug'
            }
        });

        this.setupToolHandlers();
        this.setupErrorHandling();
    }

    protected abstract getTools(): MCPTool[];
    protected abstract handleToolCall(toolName: string, args: any): Promise<any>;

    private setupToolHandlers() {
        this.server.setRequestHandler(ListToolsRequestSchema, async () => {
            return {
                tools: this.getTools()
            };
        });

        this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
            const { name, arguments: args } = request.params;

            try {
                return await this.handleToolCall(name, args);
            } catch (error) {
                console.error(`Error in tool ${name}:`, error);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`
                        }
                    ]
                };
            }
        });
    }

    private setupErrorHandling() {
        this.server.onerror = (error) => {
            console.error('[MCP Error]', error);
        };

        process.on('SIGINT', async () => {
            console.log(`\nShutting down ${this.serviceName}...`);
            await this.server.close();
            process.exit(0);
        });

        process.on('SIGTERM', async () => {
            console.log(`\nShutting down ${this.serviceName}...`);
            await this.server.close();
            process.exit(0);
        });
    }

    private async setupFastifyPlugins() {
        await this.app.register(cors, {
            origin: true,
            credentials: true
        });
    }

    protected createSuccessResponse(content: string) {
        return {
            content: [
                {
                    type: 'text',
                    text: content
                }
            ]
        };
    }

    protected createErrorResponse(error: string) {
        return {
            content: [
                {
                    type: 'text',
                    text: `Error: ${error}`
                }
            ]
        };
    }

    async start() {
        await this.setupFastifyPlugins();

        this.app.get('/sse', async (request: FastifyRequest, reply: FastifyReply) => {
            const transport = new SSEServerTransport('/sse', reply.raw);
            await this.server.connect(transport);
        });

        this.app.get('/health', async (request: FastifyRequest, reply: FastifyReply) => {
            return { status: 'healthy', service: this.serviceName };
        });

        try {
            await this.app.listen({
                host: this.host,
                port: this.port
            });
            console.log(`${this.serviceName} MCP server is running on http://${this.host}:${this.port}/sse`);
        } catch (error) {
            console.error(`Error starting ${this.serviceName} server:`, error);
            process.exit(1);
        }
    }
}