import { MongoDBChatMessageHistory } from '@langchain/mongodb';

export interface IChatHistoryService {
    getChatHistory(userId: string, collectionId: string): Promise<MongoDBChatMessageHistory>;
    buildContextMessages(allMessages: any[]): Promise<any[]>;
    saveConversation(chatHistory: MongoDBChatMessageHistory, userQuery: string, agentResponse: string): Promise<void>;
}

export interface ChatHistoryConfig {
    shortTermLimit?: number;
    summaryChunkSize?: number;
    summaryWordLimit?: number;
}