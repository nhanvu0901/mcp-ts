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
import { mkdir, access } from 'fs/promises';
import api from "./routes/index";
import dotenv from 'dotenv';
import fp from 'fastify-plugin';
import errorHandlerPlugin from './plugins/errorHandler.plugin'
dotenv.config();

const config = {
    HOST: process.env.HOST || '0.0.0.0',
    PORT: parseInt(process.env.PORT || '3000'),
    NODE_ENV: process.env.NODE_ENV || 'development',

    AZURE_OPENAI_API_KEY: process.env.AZURE_OPENAI_API_KEY!,
    AZURE_OPENAI_ENDPOINT: process.env.AZURE_OPENAI_ENDPOINT!,
    AZURE_OPENAI_MODEL_NAME: process.env.AZURE_OPENAI_MODEL_NAME || 'gpt-4',
    AZURE_OPENAI_MODEL_API_VERSION: process.env.AZURE_OPENAI_MODEL_API_VERSION || '2024-02-15-preview',

    DOCUMENT_MCP_URL: process.env.DOCUMENT_MCP_URL || 'http://localhost:8001/sse',
    RAG_MCP_URL: process.env.RAG_MCP_URL || 'http://localhost:8002/sse',
    DOCDB_SUMMARIZATION_MCP_URL: process.env.DOCDB_SUMMARIZATION_MCP_URL || 'http://localhost:8003/sse',

    MAX_FILE_SIZE: parseInt(process.env.MAX_FILE_SIZE || '10485760'), // 10MB
    UPLOAD_DIR: process.env.UPLOAD_DIR || '/app/data/uploads',

    DEFAULT_COLLECTION_NAME: process.env.DEFAULT_COLLECTION_NAME || 'RAG',
};
async function setupDirectories() {
    try {
        await mkdir(config.UPLOAD_DIR, { recursive: true });
        console.log(`Upload directory ensured: ${config.UPLOAD_DIR}`);
    } catch (error) {
        console.error('Failed to create upload directory:', error);
        throw error;
    }
}
function validateConfig() {
    const required = [
        'AZURE_OPENAI_API_KEY',
        'AZURE_OPENAI_ENDPOINT',
    ];

    const missing = required.filter(key => !process.env[key]);
    if (missing.length > 0) {
        throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
    }
}

function setupModel(): AzureChatOpenAI {
    return new AzureChatOpenAI({
        model: config.AZURE_OPENAI_MODEL_NAME,
        apiKey: config.AZURE_OPENAI_API_KEY,
        openAIApiVersion: config.AZURE_OPENAI_MODEL_API_VERSION,
        azureOpenAIApiInstanceName: config.AZURE_OPENAI_ENDPOINT.split('//')[1].split('.')[0],
        azureOpenAIApiDeploymentName: config.AZURE_OPENAI_MODEL_NAME,
        temperature: 0.1,
        maxTokens: 5000,
    });
}

async function setupMCPClient(): Promise<MultiServerMCPClient> {
    const client = new MultiServerMCPClient({
        DocumentService: {
            url: config.DOCUMENT_MCP_URL,
            transport: 'sse',
        },
        RAGService: {
            url: config.RAG_MCP_URL,
            transport: 'sse',
        },
        // DocDBSummarizationService: {
        //     url: config.DOCDB_SUMMARIZATION_MCP_URL,
        //     transport: 'sse',
        // }
        //TODO translation service
        //TODO history
    });

    console.log('Connecting to MCP servers...');
    // The client will connect when we call getTools()
    return client;
}

async function setupAgent(model: AzureChatOpenAI, mcpClient: MultiServerMCPClient) {
    try {
        console.log('Getting tools from MCP servers...');
        const tools = await mcpClient.getTools();
        console.log(`Loaded ${tools.length} tools from MCP servers`);

        const agentPrompt = `You are an AI assistant with connection to these services:
- DocumentService: for processing and uploading documents  
- RAGService: for querying the vector database
- DocDBSummarizationService: for summarizing documents, given a document_id

If the user asks you to summarize a document and they provide a document id, use the DocDBSummarizationService.
If the user asks you to answer a question, use the RAGService to query the vector database and answer questions related to user's personal documents.
If the user wants to upload a document, guide them to use the upload endpoint.
Always be helpful and provide accurate responses based on the available tools.`;

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
    console.log('Setting up Azure OpenAI model...');
    const model = setupModel();

    console.log('Setting up MCP client...');
    const mcpClient = await setupMCPClient();

    console.log('Setting up LangGraph agent...');
    const agent = await setupAgent(model, mcpClient);

    fastify.decorate('model', model);
    fastify.decorate('mcpClient', mcpClient);
    fastify.decorate('agent', agent);


    fastify.addHook('onClose', async () => {
        console.log('Closing AI services...');
    });
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
    // Graceful shutdown
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