export interface MCPServerConfig {
    serviceName: string;
    port: number;
    host?: string;
}

export interface VectorSearchResult {
    score: number;
    payload: Record<string, any>;
    id: string | number;
}

export interface EmbeddingConfig {
    model: string;
    endpoint: string;
    apiKey: string;
    apiVersion: string;
}

export interface QdrantConfig {
    host: string;
    port: number;
    collectionName: string;
}

export interface MCPResponse {
    content: Array<{
        type: 'text';
        text: string;
    }>;
}

export interface DocumentMetadata {
    filename: string;
    document_id: string;
    user_id?: string;
    session_id?: string;
    chunk_index?: number;
    file_type?: string;
}

export const DEFAULT_PORTS = {
    DOCUMENT: 8001,
    RAG: 8002,
    SUMMARIZATION: 8003,
} as const;