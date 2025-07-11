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
    description: 'Query the Qdrant vector database with a text query and return matching results from user documents',
    parameters: z.object({
        query: z.string().describe('The text query to search for'),
        user_id: z.string().describe('User ID to search documents for'),
        limit: z.number().default(5).describe('Maximum number of results to return')
    }),
    execute: async (args: any) => {
        try {
            const { query, user_id, limit = 5 } = args;
            const userCollectionName = `user_${user_id}_docs`;

            const collections = await qdrantClient.getCollections();
            const collectionExists = collections.collections.some(c => c.name === userCollectionName);

            if (!collectionExists) {
                return `No documents found for user "${user_id}". Collection "${userCollectionName}" does not exist yet. Please upload some documents first.`;
            }

            const collectionInfo = await qdrantClient.getCollection(userCollectionName);
            const queryEmbedding = await embeddingModel.embedQuery(query);

            const searchResults = await qdrantClient.search(userCollectionName, {
                vector: queryEmbedding,
                limit: limit,
                with_payload: true,
                score_threshold: 0.3,
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
                return `No relevant documents found for "${query}" in user ${user_id}'s documents. The database contains ${collectionInfo.points_count} documents, but none match your query. Try different keywords or upload documents about this topic.`;
            }

            return `Found ${results.length} relevant documents from user ${user_id}'s collection:\n\n${results.join('\n\n---\n\n')}`;

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

mcp.addTool({
    name: 'check_database',
    description: 'Check the status of the vector database for a specific user and see how many documents are stored',
    parameters: z.object({
        user_id: z.string().describe('User ID to check documents for')
    }),
    execute: async (args: any) => {
        try {
            const { user_id } = args;
            const userCollectionName = `user_${user_id}_docs`;

            const collections = await qdrantClient.getCollections();
            const collectionExists = collections.collections.some(c => c.name === userCollectionName);

            if (!collectionExists) {
                return `Database status for user "${user_id}": Collection "${userCollectionName}" does not exist. No documents have been uploaded yet.`;
            }

            const collectionInfo = await qdrantClient.getCollection(userCollectionName);
            return `Database status for user "${user_id}": Collection "${userCollectionName}" exists with ${collectionInfo.points_count} documents stored.`;

        } catch (error) {
            return `Error checking database: ${error instanceof Error ? error.message : 'Unknown error'}`;
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