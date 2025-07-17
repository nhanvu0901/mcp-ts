export interface SourceReference {
    document_name: string;
    page_number?: number;
    chunk_id?: number;
    source_reference: string;
    reference_type: 'page' | 'chunk';
}

export interface AskAgentBody {
    query: string;
    user_id: string;
    collection_id: string;
}

export interface AskAgentResponse {
    success: boolean;
    response?: string;
    user_id?: string;
    collection_id?: string;
    timestamp?: string;
    source_references?: SourceReference[];
    sources_count?: number;
    error?: string;
}