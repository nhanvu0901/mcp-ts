import { FastMCP } from 'fastmcp';
import { QdrantClient } from '@qdrant/js-client-rest';
import { AzureOpenAIEmbeddings } from '@langchain/openai';
import { z } from 'zod';
import dotenv from 'dotenv';

dotenv.config();

const mcp = new FastMCP({
    name: "RAGService",
    version: "1.0.0",
    instructions: "This is a RAG (Retrieval-Augmented Generation) service that can search and retrieve relevant document chunks based on queries.",
});

const COLLECTION_NAME = "RAG";

const qdrantClient = new QdrantClient({
    host: process.env.QDRANT_HOST || "localhost",
    port: parseInt(process.env.QDRANT_PORT || "6333"),
});

const embeddingModel = new AzureOpenAIEmbeddings({
    model: process.env.AZURE_OPENAI_EMBEDDING_DEPLOYMENT!,
    azureOpenAIEndpoint: process.env.AZURE_OPENAI_EMBEDDING_ENDPOINT!,
    azureOpenAIApiKey: process.env.AZURE_OPENAI_EMBEDDING_API_KEY!,
    azureOpenAIApiVersion: process.env.AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION!,
});

mcp.addTool({
    name: 'retrieve',
    description: 'Query the Qdrant vector database with a text query and return matching results',
    parameters: z.object({
        query: z.string().describe('The text query to search for'),
        limit: z.number().default(5).describe('Maximum number of results to return')
    }),
    execute: async (args: any) => {
        try {
            const { query, limit = 5 } = args;

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

            return results.join('\n');

        } catch (error) {
            console.error('Error during query:', error);
            throw new Error(`Retrieval failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }
});

if (require.main === module) {
    console.log("RAG Service MCP server is running on http://0.0.0.0:8002");
    mcp.start({
        transportType: "httpStream",
        httpStream: {
            port: 8002,

        }
    });
}

export default mcp;