import 'reflect-metadata';
import fastify, {type FastifyInstance} from 'fastify';
import multipart from '@fastify/multipart';
import cors from '@fastify/cors';
import helmet from '@fastify/helmet';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';
import {createReactAgent} from '@langchain/langgraph/prebuilt';
import {MultiServerMCPClient} from '@langchain/mcp-adapters';
import {MongoClient} from 'mongodb';
import {mkdir} from 'fs/promises';
import api from "./routes/index";
import dotenv from 'dotenv';
import fp from 'fastify-plugin';
import errorHandlerPlugin from './plugins/errorHandler.plugin';
import { ChatOpenAI } from '@langchain/openai';

dotenv.config();

function cleanEnvVar(value: string | undefined, defaultValue: string = ''): string {
    if (!value) return defaultValue;
    return value.replace(/^["']|["']$/g, '').trim();
}

const config = {
    HOST: process.env.HOST || '0.0.0.0',
    PORT: parseInt(process.env.PORT || '3000'),
    NODE_ENV: process.env.NODE_ENV || 'development',
    DEBUG: process.env.DEBUG,

    // LiteLLM Proxy Configuration
    LITELLM_PROXY_URL: cleanEnvVar(process.env.LITELLM_PROXY_URL, 'http://localhost:4000'),
    LITELLM_MASTER_KEY: cleanEnvVar(process.env.LITELLM_MASTER_KEY, 'sk-1234567890abcdef'),
    AZURE_OPENAI_MODEL_NAME: cleanEnvVar(process.env.AZURE_OPENAI_MODEL_NAME, 'ace-gpt-4o'),

    // MCP Service URLs
    RAG_MCP_URL: process.env.RAG_MCP_URL || 'http://localhost:8002/sse',
    DOCDB_SUMMARIZATION_MCP_URL: process.env.DOCDB_SUMMARIZATION_MCP_URL || 'http://localhost:8003/sse',
    DOCUMENT_TRANSLATION_MCP_URL: process.env.DOCUMENT_TRANSLATION_MCP_URL || 'http://localhost:8004/sse',

    // Application Settings
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
    const required = ['LITELLM_PROXY_URL', 'LITELLM_MASTER_KEY'];
    const missing = required.filter(key => !process.env[key]);
    if (missing.length > 0) {
        throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
    }
}

async function setupDebugHooks(server: FastifyInstance): Promise<void> {
    const debugEnabled = config.DEBUG === 'true' || config.NODE_ENV === 'development';

    if (!debugEnabled) return;

    server.addHook('onRequest', async (request, reply) => {
        (request as any).debugInfo = {
            startTime: process.hrtime.bigint()
        };
    });

    server.addHook('preHandler', async (request, reply) => {
        request.log.debug({
            requestId: request.id,
            method: request.method,
            url: request.url,
            body: request.body,
            bodySize: request.body ? `${Buffer.byteLength(JSON.stringify(request.body))} bytes` : '0 bytes',
            contentType: request.headers['content-type'],
            isMultipart: request.isMultipart(),
        }, 'REQUEST BODY DATA');
    });

    server.addHook('onSend', async (request, reply, payload) => {
        let responseBody: any = payload;
        let responseSize = 0;
        try {
            if (typeof payload === 'string') {
                responseSize = Buffer.byteLength(payload);
                if (responseSize < 10000) {
                    try {
                        responseBody = JSON.parse(payload);
                    } catch {
                        responseBody = payload;
                    }
                } else {
                    responseBody = `[Large response: ${responseSize} bytes]`;
                }
            } else if (Buffer.isBuffer(payload)) {
                responseSize = payload.length;
                responseBody = `[Buffer: ${responseSize} bytes]`;
            } else if (payload && typeof payload === 'object') {
                const payloadStr = JSON.stringify(payload);
                responseSize = Buffer.byteLength(payloadStr);
                responseBody = responseSize < 10000 ? payload : `[Large object: ${responseSize} bytes]`;
            }

            request.log.debug({
                requestId: request.id,
                method: request.method,
                url: request.url,
                statusCode: reply.statusCode,
                responseBody: responseBody,
                responseSize: `${responseSize} bytes`,
                contentType: reply.getHeader('content-type'),
                timestamp: new Date().toISOString()
            }, 'RESPONSE BODY DATA');
        } catch (error) {
            request.log.warn({
                requestId: request.id,
            }, 'Failed to log response body '+error);
        }
        return payload;
    });

    server.addHook('onError', async (request, reply, error) => {
        const debugInfo = (request as any).debugInfo;
        const errorTime = debugInfo ? process.hrtime.bigint() : process.hrtime.bigint();
        const duration = debugInfo ? Number(errorTime - debugInfo.startTime) / 1000000 : 0;

        request.log.error({
            requestId: request.id,
            method: request.method,
            url: request.url,
            errorName: error.name,
            errorMessage: error.message,
            errorCode: (error as any).code || 'UNKNOWN',
            statusCode: (error as any).statusCode || 500,
            stack: error.stack,
            duration: `${duration.toFixed(2)}ms`,
            query: request.query,
            params: request.params,
            body: request.method !== 'GET' ? request.body : undefined,
            headers: {
                userAgent: request.headers['user-agent'],
                contentType: request.headers['content-type'],
                origin: request.headers.origin
            },
            clientIp: request.ip,
            timestamp: new Date().toISOString(),
            errorLocation: {
                function: error.stack?.split('\n')[1]?.trim(),
                file: error.stack?.split('\n')[1]?.match(/\((.+):\d+:\d+\)/)?.[1]
            }
        },'ERROR DATA');
    });

    server.addHook('onTimeout', async (request, reply) => {
        request.log.warn({
            requestId: request.id,
            method: request.method,
            url: request.url,
            timeout: server.server.timeout,
            timestamp: new Date().toISOString()
        },'TIMEOUT');
    });
}

function setupModel(): ChatOpenAI {
    return new ChatOpenAI({
        model: config.AZURE_OPENAI_MODEL_NAME,
        apiKey: config.LITELLM_MASTER_KEY,
        configuration: {
            baseURL: config.LITELLM_PROXY_URL + '/v1',
        },
        temperature: 0.1,
        maxTokens: 5000,
        timeout: 30000,
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

async function setupAgent(model: ChatOpenAI, mcpClient: MultiServerMCPClient) {
    try {
        const tools = await mcpClient.getTools();
        console.log(`Loaded ${tools.length} tools from MCP servers`);

        const agentPrompt = `You are an AI assistant with access to RAGService (document search), DocDBSummarizationService (document summarization), and DocumentTranslationService (document translation). **Always check conversation history context FIRST before using external services.**

**Query Types:**
1. **Document-Specific**: Messages containing "Document ID:" target a specific document
2. **General**: No Document ID means search across all user documents
3. **Multi-Collection**: The collection_id parameter is always a list of collection IDs (UUIDs). You must always send a list, even if there is only one collection.

**Collection ID Format:**
- The collection_id is always a list of UUIDs (universally unique identifiers). Treat these as unique database identifiers, not as document names or user-friendly labels. Do not attempt to parse or interpret them as anything else. Never send a single string; always send a list.

**Document-Specific Processing:**
When Document ID is present:
- ALWAYS use the provided document_id for MCP calls, regardless of document names in query text
- IGNORE document names in query text - document_id is authoritative
- Summarization: Use DocDBSummarizationService with document_id
- Translation: Use DocumentTranslationService with document_id
- Other questions: Use RAGService for the specific document

**General Processing:**
Use RAGService to search across all documents in user's collection.

**Multi-Collection Processing:**
When collection_id is a list, RAGService will search across all specified collections, merge the results, and return the most relevant ones. You should treat the aggregated results as a unified set and present the top answers to the user, regardless of which collection they came from.

**Translation Response Rules:**
When using DocumentTranslationService:
- ALWAYS return the COMPLETE translated text in your response
- DO NOT just provide a summary or word count
- Include the full translation content for the user to read
- Format the translation clearly and readably

**Citation Rules:**
RAGService returns text with "SOURCE_CITATION: \\cite{document_name, page/chunk number}". You MUST:
1. Preserve exact "SOURCE_CITATION:" prefix format
2. Place citations immediately after supported claims
3. DO NOT group citations at end
4. Each claim needs its citation right after

**Example:**
Simple reflex agents act based on current percepts. SOURCE_CITATION: \\cite{ai agent.pdf, page 1} Model-based agents maintain internal state. SOURCE_CITATION: \\cite{ai agent.pdf, page 2}

**Always prioritize conversation history over external services for personal user information.**`;

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
                        title: 'Fastify MCP RAG API with LiteLLM',
                        description: 'TypeScript/Fastify application with LangGraph, MCP integration, and LiteLLM proxy',
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
    await setupDebugHooks(server)

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
            console.log(`\n🚀 Server started successfully!`);
            console.log(`📚 API Documentation: http://${config.HOST}:${config.PORT}/docs`);
            console.log(`🔧 LiteLLM UI: ${config.LITELLM_PROXY_URL} (if enabled)`);
            console.log(`📊 MongoDB Admin: http://${config.HOST}:8081`);
            console.log(`🗄️  PostgreSQL Admin: http://${config.HOST}:8082`);
            console.log(`🔍 Qdrant Dashboard: http://${config.HOST}:6333/dashboard`);
        }

    } catch (error) {
        console.error('Error starting server:', error);
        process.exit(1);
    }
}

declare module 'fastify' {
    interface FastifyInstance {
        model: ChatOpenAI;
        mongoClient: MongoClient;
        mcpClient: MultiServerMCPClient;
        agent: any;
    }
}

if (require.main === module) {
    startServer();
}

export default buildServer;