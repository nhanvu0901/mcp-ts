import { ExtendedMongoDBChatHistory } from "../services";

export interface ExtendedChatMetadata {
    user_id?: string;
    collection_id?: string[];
    title?: string;
    doc_id?: string;
}

export interface MessageContent {
    type: "file" | "text";
    doc?: {
        doc_id: string;
    };
    text?: string;
}

export interface CustomMessage {
    role: "user" | "assistant" | "system";
    content: MessageContent[];
}

export interface IChatHistoryService {
    getChatHistory(
        userId: string,
        collectionId: string,
        metadata?: ExtendedChatMetadata
    ): Promise<ExtendedMongoDBChatHistory>;

    buildContextMessages(allMessages: any[], sessionId: string): Promise<any[]>;

    saveConversation(
        chatHistory: ExtendedMongoDBChatHistory,
        userQuery: string,
        agentResponse: string,
        sessionId: string,
        docId?: string
    ): Promise<void>;

    getUserConversations(userId: string, limit?: number): Promise<ConversationListItem[]>;

    deleteConversation(sessionId: string, userId: string): Promise<boolean>;

    updateConversationTitle(sessionId: string, userId: string, newTitle: string): Promise<boolean>;

    cleanupDuplicateEntries(): Promise<void>;
}

export interface ConversationListItem {
    sessionId: string;
    title?: string;
    messageCount: number;
    lastActivity: Date;
    collections: string[];
}

export interface StoredSummary {
    sessionId: string;
    summaryIndex: number;
    summary: string;
    messageCount: number;
    createdAt: Date;
}
