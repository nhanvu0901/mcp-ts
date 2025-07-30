import {IntentRequest, IntentType} from "./intent.types";

export interface SourceReference {
    document_name: string;
    page_number?: number;
    chunk_id?: number;
    source_reference: string;
    reference_type: 'page' | 'chunk';
    text_content?: string;
}

export interface AskAgentBody {
    query?: string; // Optional when intent is provided
    user_id: string;
    session_id?: string; // Optional - auto-generated if not provided
    collection_id?: string | string[]; // Optional
    doc_id?: string;
    intent?: IntentRequest;
}

export interface AskAgentResponse {
    success: boolean;
    response?: string;
    user_id?: string;
    session_id?: string; // Always returned
    collection_id?: string | string[];
    timestamp?: string;
    source_references?: SourceReference[];
    sources_count?: number;
    error?: string;
    query_type?: 'document_specific' | 'general' | 'intent_based';
    intent_type?: IntentType;
}

export interface ExtractedContent {
    aiResponse: string;
    ragResponse: string | null;
}

export interface AgentToolInput {
    query: string;
    user_id: string;
    collection_id?: string[]; // Optional
    doc_id?: string;
    has_document_context?: boolean;
}