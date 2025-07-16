import { MongoDBChatMessageHistory } from '@langchain/mongodb';
import { HumanMessage, AIMessage, SystemMessage } from '@langchain/core/messages';
import { MongoClient } from 'mongodb';
import { AzureChatOpenAI } from '@langchain/openai';
import { IChatHistoryService, ChatHistoryConfig } from '../types/chat-history.types';

export class ChatHistoryService implements IChatHistoryService {
    private readonly shortTermLimit: number;
    private readonly summaryChunkSize: number;
    private readonly summaryWordLimit: number;

    constructor(
        private mongoClient: MongoClient,
        private model: AzureChatOpenAI,
        config?: ChatHistoryConfig
    ) {
        this.shortTermLimit = config?.shortTermLimit ?? 10;
        this.summaryChunkSize = config?.summaryChunkSize ?? 5;
        this.summaryWordLimit = config?.summaryWordLimit ?? 50;
    }

    async getChatHistory(userId: string, collectionId: string): Promise<MongoDBChatMessageHistory> {
        const memoryCollection = this.mongoClient.db("ai_assistant").collection("chat_memory");
        return new MongoDBChatMessageHistory({
            collection: memoryCollection,
            sessionId: `${userId}_${collectionId}`,
        });
    }

    async buildContextMessages(allMessages: any[]): Promise<any[]> {
        if (allMessages.length <= this.shortTermLimit) {
            return allMessages;
        }

        const recentMessages = allMessages.slice(-this.shortTermLimit);
        const olderMessages = allMessages.slice(this.shortTermLimit, -this.shortTermLimit);

        if (olderMessages.length === 0) {
            return recentMessages;
        }

        const summaries = await this.createConversationSummaries(olderMessages);
        const contextMessages = [];

        if (summaries.length > 0) {
            const combinedSummary = summaries.join('\n\n');
            contextMessages.push(new SystemMessage(
                `Previous conversation summary:\n${combinedSummary}\n\n--- Current conversation continues below ---`
            ));
        }

        contextMessages.push(...recentMessages);
        return contextMessages;
    }

    async saveConversation(chatHistory: MongoDBChatMessageHistory, userQuery: string, agentResponse: string): Promise<void> {
        await chatHistory.addMessage(new HumanMessage(userQuery));
        await chatHistory.addMessage(new AIMessage(agentResponse));
    }

    private async createConversationSummaries(messages: any[]): Promise<string[]> {
        const summaries: string[] = [];

        for (let i = 0; i < messages.length; i += this.summaryChunkSize) {
            const chunk = messages.slice(i, i + this.summaryChunkSize);

            if (chunk.length < 2) continue;

            try {
                const summary = await this.summarizeMessageChunk(chunk);
                summaries.push(summary);
            } catch (error) {
                console.error('Error creating summary:', error);
                continue;
            }
        }

        return summaries;
    }

    private async summarizeMessageChunk(messageChunk: any[]): Promise<string> {
        const conversationText = messageChunk
            .map(msg => {
                const role = msg._getType() === 'human' ? 'User' : 'Assistant';
                return `${role}: ${msg.content}`;
            })
            .join('\n');

        const summaryPrompt = `Summarize this conversation exchange in exactly ${this.summaryWordLimit} words or less. Focus on key topics, decisions, and important context that might be referenced later:

${conversationText}

Summary:`;

        const response = await this.model.invoke([new HumanMessage(summaryPrompt)]);
        const summary = typeof response.content === 'string'
            ? response.content.trim()
            : JSON.stringify(response.content).trim();

        return summary.length > this.summaryWordLimit * 6
            ? summary.substring(0, this.summaryWordLimit * 6) + '...'
            : summary;
    }
}