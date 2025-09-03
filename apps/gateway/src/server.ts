import "reflect-metadata";
import fastify, { type FastifyInstance, type FastifyRequest, type FastifyReply } from "fastify";
import cors from "@fastify/cors";
import helmet from "@fastify/helmet";
import swagger from "@fastify/swagger";
import swaggerUi from "@fastify/swagger-ui";
import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { MultiServerMCPClient } from "@langchain/mcp-adapters";
import { MongoClient } from "mongodb";
import api from "./app/routes";
import dotenv from "dotenv";
import fp from "fastify-plugin";
import errorHandlerPlugin from "./app/plugins/errorHandler.plugin";
import { ChatOpenAI } from "@langchain/openai";
import { agentPrompt } from "./app/ai_prompt/mcp.agent.promp"
dotenv.config();

declare module "fastify" {
    interface FastifyRequest {
        mcpClient?: MultiServerMCPClient;
    }
}

function cleanEnvVar(value: string | undefined): string {
    if (!value) return '';
    return value.replace(/^["']|["']$/g, "").trim();
}

const config = {
    HOST: process.env.HOST || "0.0.0.0",
    PORT: parseInt(process.env.PORT || "3000"),
    NODE_ENV: process.env.NODE_ENV || "development",
    DEBUG: process.env.DEBUG,

    LITELLM_PROXY_URL: cleanEnvVar(process.env.LITELLM_PROXY_URL),
    LITELLM_MASTER_KEY: cleanEnvVar(process.env.LITELLM_MASTER_KEY),
    LITELLM_APP_KEY: cleanEnvVar(process.env.LITELLM_APP_KEY),

    LLM_CHAT_MODEL: cleanEnvVar(process.env.LLM_CHAT_MODEL),

    RAG_MCP_URL: process.env.RAG_MCP_URL as string,
    DOCDB_SUMMARIZATION_MCP_URL: process.env.DOCDB_SUMMARIZATION_MCP_URL as string,
    DOCUMENT_TRANSLATION_MCP_URL: process.env.DOCUMENT_TRANSLATION_MCP_URL as string,

    SWAGGER_HOST: process.env.SWAGGER_HOST,

    MAX_FILE_SIZE: parseInt(process.env.MAX_FILE_SIZE || "10485760"),
    MONGODB_URI:
        process.env.MONGODB_URI ||
        "mongodb://root:rootPass@mongodb:27017/ai_assistant?authSource=admin",
    DEFAULT_COLLECTION_NAME: process.env.DEFAULT_COLLECTION_NAME || "RAG",
    origin: process.env.ALLOWED_ORIGIN?.split(",") ?? "*",
};


function validateConfig() {
    const required = ["LITELLM_PROXY_URL", "LITELLM_APP_KEY"];
    const missing = required.filter(key => !process.env[key]);
    if (missing.length > 0) {
        throw new Error(`Missing required environment variables: ${missing.join(", ")}`);
    }
}

async function setupDebugHooks(server: FastifyInstance): Promise<void> {
    const debugEnabled = config.DEBUG === "true" || config.NODE_ENV === "development";

    if (!debugEnabled) return;

    server.addHook("onRequest", async (request: FastifyRequest) => {
        (request as any).debugInfo = {
            startTime: process.hrtime.bigint()
        };
    });

    server.addHook("preHandler", async (request: FastifyRequest) => {
        request.log.debug({
            requestId: request.id,
            method: request.method,
            url: request.url,
            body: request.body,
            bodySize: request.body ? `${Buffer.byteLength(JSON.stringify(request.body))} bytes` : "0 bytes",
            contentType: request.headers["content-type"],
        }, "REQUEST BODY DATA");
    });

    server.addHook("onSend", async (request: FastifyRequest, reply: FastifyReply, payload: unknown) => {
        let responseBody: any = payload;
        let responseSize = 0;
        try {
            if (typeof payload === "string") {
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
            } else if (payload && typeof payload === "object") {
                const payloadStr = JSON.stringify(payload);
                responseSize = Buffer.byteLength(payloadStr);
                responseBody = responseSize < 10000 ? payload : `[Large object: ${responseSize} bytes]`;
            }

            request.log.debug(
                {
                    requestId: request.id,
                    method: request.method,
                    url: request.url,
                    statusCode: reply.statusCode,
                    responseBody: responseBody,
                    responseSize: `${responseSize} bytes`,
                    contentType: reply.getHeader("content-type"),
                    timestamp: new Date().toISOString(),
                },
                "RESPONSE BODY DATA"
            );
        } catch (error) {
            request.log.warn(
                {
                    requestId: request.id,
                    error: String(error)
                },
                "Failed to log response body"
            );
        }
        return payload;
    });

    server.addHook("onError", async (request: FastifyRequest, reply: FastifyReply, error: Error) => {
        const debugInfo = (request as any).debugInfo;
        const errorTime = debugInfo ? process.hrtime.bigint() : process.hrtime.bigint();
        const duration = debugInfo ? Number(errorTime - debugInfo.startTime) / 1000000 : 0;

        request.log.error({
            requestId: request.id,
            method: request.method,
            url: request.url,
            errorName: error.name,
            errorMessage: error.message,
            errorCode: (error as any).code || "UNKNOWN",
            statusCode: (error as any).statusCode || 500,
            stack: error.stack,
            duration: `${duration.toFixed(2)}ms`,
            query: request.query,
            params: request.params,
            body: request.method !== "GET" ? request.body : undefined,
            headers: {
                userAgent: request.headers["user-agent"],
                contentType: request.headers["content-type"],
                origin: request.headers.origin
            },
            clientIp: request.ip,
            timestamp: new Date().toISOString(),
            errorLocation: {
                function: error.stack?.split("\n")[1]?.trim(),
                file: error.stack?.split("\n")[1]?.match(/\((.+):\d+:\d+\)/)?.[1]
            }
        }, "ERROR DATA");
    });

    server.addHook("onTimeout", async (request: FastifyRequest, reply: FastifyReply) => {
        request.log.warn({
            requestId: request.id,
            method: request.method,
            url: request.url,
            timeout: server.server.timeout,
            timestamp: new Date().toISOString()
        }, "TIMEOUT");
    });
}

function setupModel(): ChatOpenAI {
    return new ChatOpenAI({
        model: config.LLM_CHAT_MODEL,
        apiKey: config.LITELLM_APP_KEY,
        configuration: {
            baseURL: config.LITELLM_PROXY_URL + "/v1",
        },
        temperature: 0.1,
        maxTokens: 5000,
        timeout: 30000,
    });
}

async function setupMongoClient(): Promise<MongoClient> {
    const client = new MongoClient(config.MONGODB_URI, {
        driverInfo: { name: "langchainjs" },
        serverSelectionTimeoutMS: 5000,
        connectTimeoutMS: 5000,
    });

    try {
        await client.connect();
        await client.db("admin").command({ ping: 1 });
        return client;
    } catch (error) {
        console.error(`MongoDB connection failed for ${config.MONGODB_URI}:`, error);
        throw error;
    }
}

async function setupMCPClient(token: string): Promise<MultiServerMCPClient> {
    const client = new MultiServerMCPClient({
        RAGService: {
            url: config.RAG_MCP_URL,
            headers: {
                Authorization: `Bearer ${token}`,
            },
        },
        DocDBSummarizationService: {
            url: config.DOCDB_SUMMARIZATION_MCP_URL,
            headers: {
                Authorization: `Bearer ${token}`,
            },
        },
        DocumentTranslationService: {
            url: config.DOCUMENT_TRANSLATION_MCP_URL,
            headers: {
                Authorization: `Bearer ${token}`,
            },
        },
    });
    return client;
}

async function setupAgent(model: ChatOpenAI, mcpClient: MultiServerMCPClient) {
    try {
        const tools = await mcpClient.getTools();
        console.log(`Loaded ${tools.length} tools from MCP servers`);

        return createReactAgent({
            llm: model,
            tools: tools,
            prompt: agentPrompt,
        });
    } catch (error) {
        console.error("Error setting up agent:", error);
        throw error;
    }
}

const aiServicesPlugin = fp(
    async function aiServicesPlugin(fastify: FastifyInstance) {
        const model = setupModel();
        const mongoClient = await setupMongoClient();

        const apiKey = process.env.API_KEY || "";
        if (!apiKey) {
            throw new Error("API_KEY is missing in environment variables");
        }

        const mcpClient = await setupMCPClient(apiKey);
        fastify.decorate("mcpClient", mcpClient);
        const agent = await setupAgent(model, mcpClient);

        fastify.decorate("model", model);
        fastify.decorate("mongoClient", mongoClient);
        fastify.decorate("agent", agent);
    },
    {
        name: "ai-services",
        dependencies: [],
    }
);

function buildServersArray(): Array<{ url: string; description: string }> {
    const servers = [
        {
            url: `http://localhost:${config.PORT}`,
            description: "Development server",
        },
    ];

    if (config.SWAGGER_HOST) {
        servers.push({
            url: `https://${config.SWAGGER_HOST}`,
            description: "Environment server",
        });
    }

    return servers;
}

async function registerPlugins(server: FastifyInstance): Promise<void> {
    try {
        await server.register(import("@fastify/compress"), { global: false });

        await server.register(cors, { origin: config.origin });

        await server.register(helmet, {
            contentSecurityPolicy: {
                directives: {
                    defaultSrc: [`"self"`],
                    imgSrc: [`"self"`, "data:", "validator.swagger.io"],
                    scriptSrc: [`"self"`, `"unsafe-inline"`, `"unsafe-eval"`],
                    styleSrc: [`"self"`, `"unsafe-inline"`],
                    connectSrc: [`"self"`]
                }
            }
        });

        await server.register(swagger, {
            openapi: {
                openapi: "3.0.0",
                info: {
                    title: "Fastify MCP",
                    description:
                        "TypeScript/Fastify application with LangGraph, MCP integration, and LiteLLM proxy",
                    version: "1.0.0",
                },
                servers: buildServersArray(),
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
            routePrefix: "/docs",
            uiConfig: {
                docExpansion: "full",
                deepLinking: false,
            },
            staticCSP: true,
        });

        await server.register(errorHandlerPlugin);
        await server.register(aiServicesPlugin);
    } catch (error) {
        server.log.error({ error }, "Error registering plugins");
        throw error;
    }
}

async function registerRoutes(server: FastifyInstance): Promise<void> {
    try {
        await server.register(api);
    } catch (error) {
        server.log.error({ error }, "Error registering routes");
        throw error;
    }
}

async function buildServer(): Promise<FastifyInstance> {
    validateConfig();

    const server = fastify({
        logger: {
            level: config.NODE_ENV === "production" ? "info" : "debug",
            ...(config.NODE_ENV === "production" && {
                redact: ["req.headers.authorization"],
            }),
        },
        bodyLimit: config.MAX_FILE_SIZE,
        keepAliveTimeout: 30000,
        requestIdHeader: "x-request-id",
    });

    await registerPlugins(server);
    await registerRoutes(server);
    await setupDebugHooks(server);

    const gracefulShutdown = async (signal: string) => {
        server.log.info({ signal }, "Received signal, shutting down gracefully");
        try {
            await server.close();
            process.exit(0);
        } catch (error) {
            server.log.error({ error }, "Error during shutdown");
            process.exit(1);
        }
    };

    for (const signal of ["SIGINT", "SIGTERM"]) {
        process.on(signal, () => gracefulShutdown(signal));
    }

    process.on("unhandledRejection", (reason, promise) => {
        server.log.error({ reason, promise }, "Unhandled Rejection");
    });

    process.on("uncaughtException", (error) => {
        server.log.error({ error }, "Uncaught Exception");
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
        console.log(`API Documentation: http://${config.HOST}:${config.PORT}/docs`);
    } catch (error) {
        console.error("Error starting server:", error);
        process.exit(1);
    }
}

declare module "fastify" {
    interface FastifyInstance {
        model: ChatOpenAI;
        mongoClient: MongoClient;
        mcpClient: MultiServerMCPClient;
        agent: any;
    }
}


startServer();


export default buildServer;
