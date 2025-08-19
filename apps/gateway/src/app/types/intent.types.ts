export interface IntentRequest {
    intent: IntentType;
    // Summarization options
    level?: "concise" | "medium" | "detailed";
    word_count?: number;
    // Translation options
    target_language?: string;
    // Search options
    limit?: number;
}

export type IntentType = "summarise" | "translate" | "search";
