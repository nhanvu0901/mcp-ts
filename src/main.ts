import 'reflect-metadata';
import fastify, {type FastifyInstance} from 'fastify';
import multipart from '@fastify/multipart';
import cors from '@fastify/cors';
import helmet from '@fastify/helmet';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';
import {AzureChatOpenAI} from '@langchain/openai';
import {createReactAgent} from '@langchain/langgraph/prebuilt';
import {MultiServerMCPClient} from '@langchain/mcp-adapters';
import {MongoClient} from 'mongodb';
import {mkdir} from 'fs/promises';
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

    RAG_MCP_URL: process.env.RAG_MCP_URL || 'http://localhost:8002/sse',
    DOCDB_SUMMARIZATION_MCP_URL: process.env.DOCDB_SUMMARIZATION_MCP_URL || 'http://localhost:8003/sse',
    DOCUMENT_TRANSLATION_MCP_URL: process.env.DOCUMENT_TRANSLATION_MCP_URL || 'http://localhost:8004/sse',

    MAX_FILE_SIZE: parseInt(process.env.MAX_FILE_SIZE || '10485760'),
    UPLOAD_DIR: process.env.UPLOAD_DIR || './src/python/data/uploads',
    // MONGODB_URI: process.env.MONGODB_URI || 'mongodb://admin:admin123@mongodb:27017/ai_assistant?authSource=admin',
    MONGODB_URI: 'mongodb://admin:admin123@localhost:27017/ai_assistant?authSource=admin',
    DEFAULT_COLLECTION_NAME: process.env.DEFAULT_COLLECTION_NAME || 'RAG',
};

async function setupDirectories() {
    try {
        await mkdir(config.UPLOAD_DIR, {recursive: true});
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

async function setupMongoClient(): Promise<MongoClient> {
    const client = new MongoClient(config.MONGODB_URI, {
        driverInfo: {name: "langchainjs"},
        serverSelectionTimeoutMS: 5000,
        connectTimeoutMS: 5000,
    });

    try {
        await client.connect();
        await client.db("admin").command({ping: 1});
        return client;
    } catch (error) {
        console.error('MongoDB connection failed:', error);
        throw error;
    }
}

async function setupMCPClient(): Promise<MultiServerMCPClient> {
    const client = new MultiServerMCPClient({
        RAGService: {
            url: config.RAG_MCP_URL,
            transport: 'sse',
        },
        DocDBSummarizationService: {
            url: config.DOCDB_SUMMARIZATION_MCP_URL,
            transport: 'sse',
        },
        DocumentTranslationService: {
            url: config.DOCUMENT_TRANSLATION_MCP_URL,
            transport: 'sse',
        },
    });
    console.log('Connecting to MCP servers...');
    return client;
}

async function setupAgent(model: AzureChatOpenAI, mcpClient: MultiServerMCPClient) {
    try {
        const tools = await mcpClient.getTools();
        console.log(`Loaded ${tools.length} tools from MCP servers`);

        const agentPrompt = `You are an AI assistant with access to the following services:
- RAGService: Use this service to query the vector database and answer questions based on the user's personal documents.
- DocDBSummarizationService: Use this service to summarize a document when the user provides a specific document_id.
- DocumentTranslationService: Use this service to translate a document when the user provides a specific document_id.

**Important: You have access to conversation history context that appears as "Previous conversation summary" in the messages. Always check this context FIRST before using external services.**

Workflow:
1. **Check conversation history**: If the question can be answered from the conversation history context, answer directly from that context.
2. **Document-specific requests**: If the user asks to summarize or translate a document with a specific document_id, use the appropriate service.
3. **Document search**: For other questions, use the RAGService to search the user's documents.
4. **Fallback**: If neither the conversation history nor documents contain the answer, politely inform the user.

**Always prioritize conversation history context over external services for personal information about the user.**`;
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
    const mongoClient = await setupMongoClient();
    const mcpClient = await setupMCPClient();
    const agent = await setupAgent(model, mcpClient);

    fastify.decorate('model', model);
    fastify.decorate('mongoClient', mongoClient);
    fastify.decorate('mcpClient', mcpClient);
    fastify.decorate('agent', agent);
}, {
    name: 'ai-services',
    dependencies: []
});

async function registerPlugins(server: FastifyInstance): Promise<void> {
    try {
        await server.register(import('@fastify/compress'), {global: false});

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
        mongoClient: MongoClient;
        mcpClient: MultiServerMCPClient;
        agent: any;
    }
}

if (require.main === module) {
    startServer();
}

export default buildServer;