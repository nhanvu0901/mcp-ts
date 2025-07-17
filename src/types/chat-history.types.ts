import { MongoDBChatMessageHistory } from '@langchain/mongodb';

export interface IChatHistoryService {
    getChatHistory(userId: string, collectionId: string): Promise<MongoDBChatMessageHistory>;
    buildContextMessages(allMessages: any[], sessionId: string): Promise<any[]>;
    saveConversation(chatHistory: MongoDBChatMessageHistory, userQuery: string, agentResponse: string, sessionId: string): Promise<void>;
    cleanupOldSummaries(sessionId: string, keepCount?: number): Promise<void>;
}

export interface ChatHistoryConfig {
    shortTermLimit?: number;
    summaryWordLimit?: number;
}
export interface StoredSummary {
    sessionId: string;
    summaryIndex: number;
    summary: string;
    messageCount: number;
    createdAt: Date;
}