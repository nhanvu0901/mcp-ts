import 'reflect-metadata';
import fastify, { type FastifyInstance } from 'fastify';
import multipart from '@fastify/multipart';
import cors from '@fastify/cors';
import helmet from '@fastify/helmet';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';
import { AzureChatOpenAI } from '@langchain/openai';
import { createReactAgent } from '@langchain/langgraph/prebuilt';
import { MultiServerMCPClient } from '@langchain/mcp-adapters';
import { mkdir } from 'fs/promises';
import api from "./routes/index";
import dotenv from 'dotenv';
import fp from 'fastify-plugin';
import errorHandlerPlugin from './plugins/errorHandler.plugin'

dotenv.config();

function cleanEnvVar(value: string | undefined, defaultValue: string = ''): string {
    if (!value) return defaultValue;
    return value.replace(/^["']|["']$/g, '').trim();
}

const config = {
    HOST: process.env.HOST || '0.0.0.0',
    PORT: parseInt(process.env.PORT || '3000'),
    NODE_ENV: process.env.NODE_ENV || 'development',

    AZURE_OPENAI_API_KEY: cleanEnvVar(process.env.AZURE_OPENAI_API_KEY),
    AZURE_OPENAI_ENDPOINT: cleanEnvVar(process.env.AZURE_OPENAI_ENDPOINT),
    AZURE_OPENAI_MODEL_NAME: cleanEnvVar(process.env.AZURE_OPENAI_MODEL_NAME, 'gpt-4'),
    AZURE_OPENAI_MODEL_API_VERSION: cleanEnvVar(process.env.AZURE_OPENAI_MODEL_API_VERSION, '2024-02-15-preview'),

    DOCUMENT_MCP_URL: process.env.DOCUMENT_MCP_URL || 'http://localhost:8001/sse',
    RAG_MCP_URL: process.env.RAG_MCP_URL || 'http://localhost:8002/mcp',
    DOCDB_SUMMARIZATION_MCP_URL: process.env.DOCDB_SUMMARIZATION_MCP_URL || 'http://localhost:8003/sse',

    MAX_FILE_SIZE: parseInt(process.env.MAX_FILE_SIZE || '10485760'),
    UPLOAD_DIR: process.env.UPLOAD_DIR || './src/python/data/uploads',

    DEFAULT_COLLECTION_NAME: process.env.DEFAULT_COLLECTION_NAME || 'RAG',
};

async function setupDirectories() {
    try {
        await mkdir(config.UPLOAD_DIR, { recursive: true });
    } catch (error) {
        console.error('Failed to create upload directory:', error);
        throw error;
    }
}

function validateConfig() {
    const required = ['AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT'];
    const missing = required.filter(key => !cleanEnvVar(process.env[key]));
    if (missing.length > 0) {
        throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
    }
}

function setupModel(): AzureChatOpenAI {
    if (!config.AZURE_OPENAI_ENDPOINT.startsWith('https://')) {
        throw new Error(`Invalid Azure OpenAI endpoint format: ${config.AZURE_OPENAI_ENDPOINT}. Must start with https://`);
    }

    try {
        new URL(config.AZURE_OPENAI_ENDPOINT);
    } catch (error) {
        throw new Error(`Invalid Azure OpenAI endpoint URL: ${config.AZURE_OPENAI_ENDPOINT}`);
    }

    return new AzureChatOpenAI({
        model: config.AZURE_OPENAI_MODEL_NAME,
        apiKey: config.AZURE_OPENAI_API_KEY,
        azureOpenAIApiVersion: config.AZURE_OPENAI_MODEL_API_VERSION,
        azureOpenAIEndpoint: config.AZURE_OPENAI_ENDPOINT,
        azureOpenAIApiDeploymentName: config.AZURE_OPENAI_MODEL_NAME,
        temperature: 0.1,
        maxTokens: 5000,
    });
}

async function setupMCPClient(): Promise<MultiServerMCPClient> {
    return new MultiServerMCPClient({
        DocumentService: {
            url: config.DOCUMENT_MCP_URL,
            transport: 'sse',
        },
        RAGService: {
            url: config.RAG_MCP_URL,
            transport: 'http',
        },
    });
}

async function setupAgent(model: AzureChatOpenAI, mcpClient: MultiServerMCPClient) {
    try {
        const tools = await mcpClient.getTools();

        const agentPrompt = `You are an AI assistant that MUST search through user's uploaded documents before answering any question.

CRITICAL INSTRUCTIONS:
1. For ANY user question, ALWAYS use the RAG 'retrieve' tool FIRST to search the user's documents
2. IMPORTANT: When calling the 'retrieve' tool, you MUST extract the user_id from the user input and pass it as a parameter
3. The user_id will be provided in the context like "User ID: {user_id}"
4. Only after searching documents should you provide an answer
5. If the search returns relevant information, base your answer on that information
6. If the search returns no relevant information, then you may use your general knowledge
7. Always mention whether your answer comes from the user's documents or general knowledge

Available tools:
- retrieve: Search through uploaded documents (requires query and user_id parameters) - USE THIS FOR EVERY QUESTION
- check_database: Check database status for a user (requires user_id parameter)
- process_document: Upload and process new documents
- upload_and_save_to_mongo: Save documents without vectorization

Example tool usage:
When user asks "what is mcp" and user_id is "nhan", call:
retrieve(query="what is mcp", user_id="nhan")

ALWAYS search documents first using the correct user_id, then answer based on what you find.`;

        return createReactAgent({
            llm: model,
            tools: tools,
            prompt: agentPrompt,
        });
    } catch (error) {
        console.error('Error setting up agent:', error);
        throw error;
    }
}

const aiServicesPlugin = fp(async function aiServicesPlugin(fastify: FastifyInstance) {
    const model = setupModel();
    const mcpClient = await setupMCPClient();
    const agent = await setupAgent(model, mcpClient);

    fastify.decorate('model', model);
    fastify.decorate('mcpClient', mcpClient);
    fastify.decorate('agent', agent);
}, {
    name: 'ai-services',
    dependencies: []
});

async function registerPlugins(server: FastifyInstance): Promise<void> {
    try {
        await server.register(import('@fastify/compress'), { global: false });

        await server.register(cors, {
            origin: config.NODE_ENV === 'production'
                ? process.env.ALLOWED_ORIGINS?.split(',') || false
                : true,
            credentials: true,
        });

        await server.register(helmet, {
            contentSecurityPolicy: {
                directives: {
                    defaultSrc: [`'self'`],
                    imgSrc: [`'self'`, "data:", "validator.swagger.io"],
                    scriptSrc: [`'self'`, `'unsafe-inline'`, `'unsafe-eval'`],
                    styleSrc: [`'self'`, `'unsafe-inline'`],
                    connectSrc: [`'self'`]
                }
            }
        });

        await server.register(multipart, {
            limits: {
                fileSize: config.MAX_FILE_SIZE,
                files: 1,
            },
        });

        if (config.NODE_ENV !== 'production') {
            await server.register(swagger, {
                openapi: {
                    openapi: '3.0.0',
                    info: {
                        title: 'Fastify MCP RAG API',
                        description: 'TypeScript/Fastify application with LangGraph and MCP integration',
                        version: '1.0.0',
                    },
                    servers: [
                        {
                            url: `http://localhost:${config.PORT}`,
                            description: 'Development server'
                        }
                    ],
                    components: {
                        securitySchemes: {
                            bearerAuth: {
                                type: "http",
                                scheme: "bearer",
                            },
                        },
                    },
                },
            });

            await server.register(swaggerUi, {
                routePrefix: '/docs',
                uiConfig: {
                    docExpansion: 'full',
                    deepLinking: false,
                },
                staticCSP: true,
            });
        }

        await server.register(errorHandlerPlugin);
        await server.register(aiServicesPlugin);

    } catch (error) {
        server.log.error('Error registering plugins:', error);
        throw error;
    }
}

async function registerRoutes(server: FastifyInstance): Promise<void> {
    try {
        await server.register(api);
    } catch (error) {
        server.log.error("Error registering routes", error);
        throw error;
    }
}

async function buildServer(): Promise<FastifyInstance> {
    validateConfig();

    const server = fastify({
        logger: {
            level: config.NODE_ENV === 'production' ? 'info' : 'debug',
            ...(config.NODE_ENV === 'production' && {
                redact: ['req.headers.authorization'],
            }),
        },
        bodyLimit: config.MAX_FILE_SIZE,
        keepAliveTimeout: 30000,
        requestIdHeader: 'x-request-id',
    });

    await registerPlugins(server);
    await registerRoutes(server);
    await setupDirectories();

    const gracefulShutdown = async (signal: string) => {
        server.log.info(`Received ${signal}, shutting down gracefully...`);
        try {
            await server.close();
            process.exit(0);
        } catch (error) {
            server.log.error('Error during shutdown:', error);
            process.exit(1);
        }
    };

    for (const signal of ['SIGINT', 'SIGTERM']) {
        process.on(signal, () => gracefulShutdown(signal));
    }

    process.on('unhandledRejection', (reason, promise) => {
        server.log.error('Unhandled Rejection at:', promise, 'reason:', reason);
    });

    process.on('uncaughtException', (error) => {
        server.log.error('Uncaught Exception:', error);
        process.exit(1);
    });

    return server;
}

async function startServer() {
    try {
        const server = await buildServer();

        await server.listen({
            host: config.HOST,
            port: config.PORT,
        });

        if (config.NODE_ENV !== 'production') {
            console.log(`API Documentation: http://${config.HOST}:${config.PORT}/docs`);
        }

    } catch (error) {
        console.error('Error starting server:', error);
        process.exit(1);
    }
}

declare module 'fastify' {
    interface FastifyInstance {
        model: AzureChatOpenAI;
        mcpClient: MultiServerMCPClient;
        agent: any;
    }
}

if (require.main === module) {
    startServer();
}

export default buildServer;