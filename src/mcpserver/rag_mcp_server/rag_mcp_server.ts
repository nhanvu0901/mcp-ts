import { z } from 'zod';
import { QdrantClient } from '@qdrant/js-client-rest';
import { AzureOpenAIEmbeddings } from '@langchain/openai';
import { BaseMCPServer, MCPTool } from '../base-server';
import { DEFAULT_PORTS, QdrantConfig, EmbeddingConfig } from '../types/types';

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

class RAGServer extends BaseMCPServer {
    constructor() {
        super('RAGService', DEFAULT_PORTS.RAG);
    }

    protected getTools(): MCPTool[] {
        return [
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
        ];
    }

    protected async handleToolCall(toolName: string, args: any) {
        switch (toolName) {
            case 'retrieve':
                return await this.handleRetrieve(args);
            default:
                throw new Error(`Unknown tool: ${toolName}`);
        }
    }

    private async handleRetrieve(args: any) {
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

            return this.createSuccessResponse(results.join('\n'));

        } catch (error) {
            console.error('Error during query:', error);
            return this.createErrorResponse(
                `Retrieval failed: ${error instanceof Error ? error.message : 'Unknown error'}`
            );
        }
    }
}

async function main() {
    const server = new RAGServer();
    await server.start();
}

if (require.main === module) {
    main().catch(console.error);
}