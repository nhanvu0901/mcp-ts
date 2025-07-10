
export interface AskAgentBody {
    question: string;
    user_id: string;
    session_id?: string;
}

export interface AskAgentResponse {
    success: boolean;
    response?: string;
    user_id?: string;
    session_id?: string;
    timestamp?: string;
    error?: string;
}