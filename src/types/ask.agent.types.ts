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
    error?: string;
}