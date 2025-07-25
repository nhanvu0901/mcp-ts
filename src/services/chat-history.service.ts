import {MongoDBChatMessageHistory} from '@langchain/mongodb';
import {HumanMessage, AIMessage, SystemMessage} from '@langchain/core/messages';
import {MongoClient} from 'mongodb';
import {IChatHistoryService, ChatHistoryConfig} from '../types/chat.history.types';
import {StoredSummary} from '../types/chat.history.types';
import {ChatOpenAI} from '@langchain/openai';

export class ChatHistoryService implements IChatHistoryService {
    private readonly shortTermLimit: number;
    private readonly summaryWordLimit: number;
    private summariesCollection: any;

    constructor(
        private mongoClient: MongoClient,
        private model: ChatOpenAI,
        config?: ChatHistoryConfig
    ) {
        this.shortTermLimit = config?.shortTermLimit ?? 10;
        this.summaryWordLimit = config?.summaryWordLimit ?? 50;
        this.summariesCollection = this.mongoClient.db("ai_assistant").collection("chat_summaries");
    }

    async getChatHistory(userId: string, collectionId: string): Promise<MongoDBChatMessageHistory> {
        const memoryCollection = this.mongoClient.db("ai_assistant").collection("chat_memory");
        return new MongoDBChatMessageHistory({
            collection: memoryCollection,
            sessionId: `${userId}_${collectionId}`,
        });
    }

    async buildContextMessages(allMessages: any[], sessionId: string): Promise<any[]> {
        if (allMessages.length <= this.shortTermLimit) {
            return allMessages;
        }

        const recentMessages = allMessages.slice(-this.shortTermLimit);
        const olderMessagesCount = allMessages.length - this.shortTermLimit;

        if (olderMessagesCount === 0) {
            return recentMessages;
        }

        const summaries = await this.getStoredSummaries(allMessages, sessionId);
        const contextMessages = [];

        if (summaries.length > 0) {
            const combinedSummary = summaries.join('\n\n');
            contextMessages.push(new SystemMessage(
                `Previous conversation summary:\n${combinedSummary}\n\n--- Current conversation continues below ---`
            ));
        } else if (olderMessagesCount < this.shortTermLimit) {
            const unsummarizedMessages = allMessages.slice(0, olderMessagesCount);
            contextMessages.push(...unsummarizedMessages);
        }

        contextMessages.push(...recentMessages);
        return contextMessages;
    }

    async saveConversation(chatHistory: MongoDBChatMessageHistory, userQuery: string, agentResponse: string, sessionId: string): Promise<void> {
        await chatHistory.addMessage(new HumanMessage(userQuery));
        await chatHistory.addMessage(new AIMessage(agentResponse));

        const allMessages = await chatHistory.getMessages();
        await this.checkAndCreateSummary(allMessages, sessionId);
    }

    private async getStoredSummaries(allMessages: any[], sessionId: string): Promise<string[]> {
        const olderMessagesCount = allMessages.length - this.shortTermLimit;
        const summaryCount = Math.floor(olderMessagesCount / this.shortTermLimit);

        if (summaryCount === 0) {
            return [];
        }

        const summaries = await this.summariesCollection
            .find({
                sessionId,
                summaryIndex: {$lt: summaryCount}
            })
            .sort({summaryIndex: 1})
            .toArray();

        return summaries.map((s: StoredSummary) => s.summary);
    }

    private async checkAndCreateSummary(allMessages: any[], sessionId: string): Promise<void> {
        const totalMessages = allMessages.length;
        const olderMessagesCount = totalMessages - this.shortTermLimit;

        if (olderMessagesCount > 0 && olderMessagesCount % this.shortTermLimit === 0) {
            const summaryIndex = Math.floor(olderMessagesCount / this.shortTermLimit) - 1;

            const existingSummary = await this.summariesCollection.findOne({
                sessionId,
                summaryIndex
            });

            if (!existingSummary) {
                const startIndex = summaryIndex * this.shortTermLimit;
                const endIndex = startIndex + this.shortTermLimit;
                const messagesToSummarize = allMessages.slice(startIndex, endIndex);

                const summary = await this.createSummary(messagesToSummarize);

                await this.summariesCollection.insertOne({
                    sessionId,
                    summaryIndex,
                    summary,
                    messageCount: this.shortTermLimit,
                    createdAt: new Date()
                });
            }
        }
    }

    private async createSummary(messages: any[]): Promise<string> {
        const conversationText = messages
            .map(msg => {
                const role = msg._getType() === 'human' ? 'User' : 'Assistant';
                return `${role}: ${msg.content}`;
            })
            .join('\n');

        const summaryPrompt = `Summarize this conversation exchange in exactly ${this.summaryWordLimit} words or less. Focus on key topics, decisions, and important context:
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

    async cleanupOldSummaries(sessionId: string, keepCount: number = 50): Promise<void> {
        const summaries = await this.summariesCollection
            .find({sessionId})
            .sort({summaryIndex: -1})
            .skip(keepCount)
            .toArray();

        if (summaries.length > 0) {
            const oldSummaryIndexes = summaries.map((s: { summaryIndex: any; }) => s.summaryIndex);
            await this.summariesCollection.deleteMany({
                sessionId,
                summaryIndex: {$in: oldSummaryIndexes}
            });
        }
    }
}