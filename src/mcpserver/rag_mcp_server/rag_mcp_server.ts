import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import { QdrantClient } from '@qdrant/js-client-rest';
import { AzureOpenAIEmbeddings } from '@langchain/openai';
import fastify from 'fastify';
import cors from '@fastify/cors';
import dotenv from 'dotenv';

dotenv.config();

const COLLECTION_NAME = "RAG";

const qdrantClient = new QdrantClient({
    host: process.env.QDRANT_HOST || 'localhost',
    port: parseInt(process.env.QDRANT_PORT || '6333'),
});

const embeddingModel = new AzureOpenAIEmbeddings({
    model: process.env.AZURE_OPENAI_EMBEDDING_DEPLOYMENT || 'text-embedding-ada-002',
    azureOpenAIEndpoint: process.env.AZURE_OPENAI_EMBEDDING_ENDPOINT!,
    azureOpenAIApiKey: process.env.AZURE_OPENAI_EMBEDDING_API_KEY!,
    azureOpenAIApiVersion: process.env.AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION || '2024-02-01',
});

const RetrieveArgsSchema = z.object({
    query: z.string().describe("The text query to search for"),
    limit: z.number().default(5).describe("Maximum number of results to return")
});

const server = new Server({
    name: 'RAGService',
    version: '1.0.0',
}, {
    capabilities: {
        tools: {},
    },
});

server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: [
            {
                name: 'retrieve',
                description: 'Query the Qdrant vector database with a text query and return matching results',
                inputSchema: {
                    type: 'object',
                    properties: {
                        query: {
                            type: 'string',
                            description: 'The text query to search for'
                        },
                        limit: {
                            type: 'number',
                            description: 'Maximum number of results to return',
                            default: 5
                        }
                    },
                    required: ['query']
                }
            }
        ]
    };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    if (name === 'retrieve') {
        try {
            const { query, limit } = RetrieveArgsSchema.parse(args);

            const queryEmbedding = await embeddingModel.embedQuery(query);

            const searchResults = await qdrantClient.search(COLLECTION_NAME, {
                vector: queryEmbedding,
                limit: limit,
                with_payload: true
            });

            const results: string[] = [];

            for (const result of searchResults) {
                if (result.payload?.text) {
                    results.push(result.payload.text as string);
                } else if (result.payload?.content) {
                    results.push(result.payload.content as string);
                } else if (result.payload) {
                    results.push(JSON.stringify(result.payload));
                }
            }

            return {
                content: [
                    {
                        type: 'text',
                        text: results.join('\n')
                    }
                ]
            };

        } catch (error) {
            console.error('Error during query:', error);
            return {
                content: [
                    {
                        type: 'text',
                        text: `Retrieval failed: ${error instanceof Error ? error.message : 'Unknown error'}`
                    }
                ]
            };
        }
    }

    throw new Error(`Unknown tool: ${name}`);
});

server.onerror = (error) => {
    console.error('[MCP Error]', error);
};

const app = fastify({
    logger: {
        level: process.env.NODE_ENV === 'production' ? 'info' : 'debug'
    }
});

async function setupServer() {
    await app.register(cors, {
        origin: true,
        credentials: true
    });

    app.all('/sse', async (request, reply) => {
        const transport = new SSEServerTransport('/sse', reply.raw);
        await server.connect(transport);
        console.log('New SSE connection established');
    });


    const gracefulShutdown = async (signal: string) => {
        console.log(`\nReceived ${signal}, shutting down RAGService...`);
        try {
            await server.close();
            await app.close();
            process.exit(0);
        } catch (error) {
            console.error('Error during shutdown:', error);
            process.exit(1);
        }
    };

    process.on('SIGINT', () => gracefulShutdown('SIGINT'));
    process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));

    try {
        await app.listen({
            host: '0.0.0.0',
            port: 8002
        });
        console.log('RAGService MCP server is running on http://0.0.0.0:8002/sse');
    } catch (error) {
        console.error('Error starting RAGService server:', error);
        process.exit(1);
    }
}

setupServer().catch(console.error);