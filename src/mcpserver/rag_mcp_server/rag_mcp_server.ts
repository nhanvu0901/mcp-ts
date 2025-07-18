import { FastMCP } from 'fastmcp';
import { QdrantClient } from '@qdrant/js-client-rest';
import { AzureOpenAIEmbeddings } from '@langchain/openai';
import { z } from 'zod';
import dotenv from 'dotenv';

dotenv.config();

function cleanEnvVar(value: string | undefined, defaultValue: string = ''): string {
    if (!value) return defaultValue;
    return value.replace(/^["']|["']$/g, '').trim();
}

const mcp = new FastMCP({
    name: "RAGService",
    version: "1.0.0",
    instructions: "This is a RAG (Retrieval-Augmented Generation) service that can search and retrieve relevant document chunks based on queries.",
});

const qdrantClient = new QdrantClient({
    host: process.env.QDRANT_HOST || "localhost",
    port: parseInt(process.env.QDRANT_PORT || "6333"),
    timeout: 10000,
});

const extractInstanceName = (endpoint: string): string => {
    try {
        const url = new URL(endpoint);
        return url.hostname.split('.')[0];
    } catch {
        return endpoint.replace('https://', '').split('.')[0];
    }
};

const embeddingEndpoint = cleanEnvVar(process.env.AZURE_OPENAI_EMBEDDING_ENDPOINT);
const embeddingApiKey = cleanEnvVar(process.env.AZURE_OPENAI_EMBEDDING_API_KEY);
const embeddingDeployment = cleanEnvVar(process.env.AZURE_OPENAI_EMBEDDING_DEPLOYMENT);
const embeddingApiVersion = cleanEnvVar(process.env.AZURE_OPENAI_EMBEDDING_MODEL_API_VERSION);

const embeddingModel = new AzureOpenAIEmbeddings({
    model: embeddingDeployment,
    azureOpenAIEndpoint: embeddingEndpoint,
    azureOpenAIApiKey: embeddingApiKey,
    azureOpenAIApiVersion: embeddingApiVersion,
    azureOpenAIApiInstanceName: extractInstanceName(embeddingEndpoint),
    azureOpenAIApiDeploymentName: embeddingDeployment,
    timeout: 15000,
});

async function testConnections() {
    try {
        await qdrantClient.getCollections();
        await embeddingModel.embedQuery("test");
    } catch (error) {
        console.error('Connection test failed:', error);
    }
}

mcp.addTool({
    name: 'retrieve',
    description: 'Query the Qdrant vector database with a text query and return matching results from user documents in a specific collection',
    parameters: z.object({
        query: z.string().describe('The text query to search for'),
        user_id: z.string().describe('User ID to search documents for'),
        collection_id: z.string().describe('Collection ID to search within'),
        limit: z.number().default(5).describe('Maximum number of results to return')
    }),
    execute: async (args: any) => {
        try {
            const { query, user_id, collection_id, limit = 5 } = args;

            const collections = await qdrantClient.getCollections();
            const collectionExists = collections.collections.some(c => c.name === collection_id);

            if (!collectionExists) {
                return `No collection "${collection_id}" found. Please ensure the collection exists and upload some documents first.`;
            }

            const collectionInfo = await qdrantClient.getCollection(collection_id);
            const queryEmbedding = await embeddingModel.embedQuery(query);

            const searchResults = await qdrantClient.search(collection_id, {
                vector: queryEmbedding,
                limit: limit,
                with_payload: true,
                score_threshold: 0.3,
                filter: {
                    must: [
                        {
                            key: "user_id",
                            match: {
                                value: user_id
                            }
                        }
                    ]
                }
            });

            const results: string[] = [];
            for (const result of searchResults) {
                if (result.payload?.text) {
                    results.push(`[Relevance: ${result.score?.toFixed(3)}] ${result.payload.text}`);
                } else if (result.payload?.content) {
                    results.push(`[Relevance: ${result.score?.toFixed(3)}] ${result.payload.content}`);
                } else if (result.payload) {
                    results.push(`[Relevance: ${result.score?.toFixed(3)}] ${JSON.stringify(result.payload)}`);
                }
            }

            if (results.length === 0) {
                return `No relevant documents found for "${query}" in collection "${collection_id}" for user "${user_id}". The collection contains ${collectionInfo.points_count} total documents, but none match your query or belong to your user account. Try different keywords or upload documents about this topic.`;
            }

            return `Found ${results.length} relevant documents from collection "${collection_id}" for user "${user_id}":\n\n${results.join('\n\n---\n\n')}`;

        } catch (error) {
            if (error instanceof Error) {
                if (error.message.includes('timeout')) {
                    return 'Search request timed out. Please try again with a simpler query.';
                }
                if (error.message.includes('collection')) {
                    return 'Database collection not found. Please upload documents first.';
                }
            }
            throw new Error(`Retrieval failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }
});


if (require.main === module) {
    testConnections().then(() => {
        mcp.start({
            transportType: "httpStream",
            httpStream: {
                port: 8002,
            }
        });
    });
}

export default mcp;