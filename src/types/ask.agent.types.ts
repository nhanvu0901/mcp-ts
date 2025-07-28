export interface SourceReference {
    document_name: string;
    page_number?: number;
    chunk_id?: number;
    source_reference: string;
    reference_type: 'page' | 'chunk';
    text_content: string;
}

export interface AskAgentBody {
    query: string;
    user_id: string;
    collection_id: string | string[];
    doc_id?: string;
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
    query_type?: 'document_specific' | 'general';
}

export interface ExtractedContent {
    aiResponse: string;
    ragResponse: string | null;
}


export interface AgentToolInput {
    query: string;
    user_id: string;
    collection_id: string[];
    doc_id?: string;
    has_document_context?: boolean;
}