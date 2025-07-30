import {MongoDBChatMessageHistory} from '@langchain/mongodb';
import {BaseMessage, HumanMessage, AIMessage, SystemMessage} from '@langchain/core/messages';
import {Collection} from 'mongodb';
import {MongoClient} from 'mongodb';
import {ChatOpenAI} from '@langchain/openai';
import {
    ExtendedChatMetadata,
    MessageContent,
    CustomMessage,
    IChatHistoryService,
    ConversationListItem,
    StoredSummary
} from "../types/chat.history.types";


export class ExtendedMongoDBChatHistory extends MongoDBChatMessageHistory {
    private metadata: ExtendedChatMetadata;
    private mongoCollection: Collection;

    constructor(fields: {
        collection: Collection;
        sessionId: string;
        metadata?: ExtendedChatMetadata;
    }) {
        super({
            collection: fields.collection,
            sessionId: fields.sessionId,
        });

        this.mongoCollection = fields.collection;
        this.metadata = fields.metadata || {};

        this.initializeSession(fields.sessionId);
    }

    private getSessionId(): string {
        return (this as any).sessionId;
    }

    private async initializeSession(sessionId: string): Promise<void> {
        try {
            const existingSession = await this.mongoCollection.findOne({ sessionId: sessionId });

            if (!existingSession && this.metadata.user_id) {
                await this.mongoCollection.insertOne({
                    sessionId: sessionId,
                    user_id: this.metadata.user_id,
                    collection_id: this.metadata.collection_id || [], // Can be empty array
                    title: this.metadata.title || null,
                    messages: [],
                    CreatedAt: new Date(),
                    UpdatedAt: new Date()
                });
            }
        } catch (error) {
            console.warn('Failed to initialize session:', error);
        }
    }

    override async addMessage(message: BaseMessage): Promise<void> {
        try {
            const customMessage = this.convertToCustomMessage(message);

            const updateFields: any = {
                UpdatedAt: new Date(),
                $push: { messages: customMessage }
            };

            if (this.metadata.user_id) {
                updateFields.user_id = this.metadata.user_id;
            }

            if (this.metadata.collection_id) {
                updateFields.collection_id = this.metadata.collection_id;
            }

            if (this.metadata.title) {
                updateFields.title = this.metadata.title;
            }

            await this.mongoCollection.updateOne(
                { sessionId: this.getSessionId() },
                {
                    $set: {
                        UpdatedAt: updateFields.UpdatedAt,
                        ...(updateFields.user_id && { user_id: updateFields.user_id }),
                        ...(updateFields.collection_id && { collection_id: updateFields.collection_id }),
                        ...(updateFields.title && { title: updateFields.title })
                    },
                    $push: { messages: customMessage as any}
                },
                { upsert: true }
            );
        } catch (error) {
            console.error('Error adding custom message:', error);
        }
    }

    override async getMessages(): Promise<BaseMessage[]> {
        try {
            const session = await this.mongoCollection.findOne(
                { sessionId: this.getSessionId() },
                { projection: { messages: 1 } }
            );

            if (!session?.messages) {
                return [];
            }

            return session.messages.map((msg: CustomMessage) => {
                const textContent = msg.content.find(c => c.type === 'text')?.text || '';

                switch (msg.role) {
                    case 'user':
                        return new HumanMessage(textContent);
                    case 'assistant':
                        return new AIMessage(textContent);
                    case 'system':
                        return new SystemMessage(textContent);
                    default:
                        return new HumanMessage(textContent);
                }
            });
        } catch (error) {
            console.warn('Failed to get messages:', error);
            return [];
        }
    }

    private convertToCustomMessage(message: BaseMessage): CustomMessage {
        const role = message instanceof HumanMessage ? 'user' :
                    message instanceof AIMessage ? 'assistant' : 'system';

        const content: MessageContent[] = [];

        if (role === 'user' && this.metadata.doc_id) {
            content.push({
                type: 'file',
                doc: {
                    doc_id: this.metadata.doc_id
                }
            });
        }

        content.push({
            type: 'text',
            text: typeof message.content === 'string' ? message.content : JSON.stringify(message.content)
        });

        return {
            role,
            content
        };
    }

    updateMetadata(metadata: Partial<ExtendedChatMetadata>): void {
        this.metadata = { ...this.metadata, ...metadata };
    }

    async setTitleFromMessage(message: string, maxLength: number = 50): Promise<void> {
        try {
            // Check if title already exists in database
            const existingSession = await this.mongoCollection.findOne(
                { sessionId: this.getSessionId() },
                { projection: { title: 1, messages: 1 } }
            );

            // Only set title if it doesn't exist AND this is the first user message
            if (!existingSession?.title && (!existingSession?.messages || existingSession.messages.length === 0)) {
                const cleanMessage = message
                    .replace(/^(User ID:|Collection ID:|Document ID:|Has Document Context:).*?\n\n/g, '')
                    .trim();

                const title = cleanMessage.length > maxLength
                    ? cleanMessage.substring(0, maxLength).trim() + '...'
                    : cleanMessage.trim();

                this.metadata.title = title;

                await this.mongoCollection.updateOne(
                    { sessionId: this.getSessionId() },
                    {
                        $set: {
                            title: title,
                            UpdatedAt: new Date()
                        }
                    }
                );
            }
        } catch (error) {
            console.warn('Failed to set title:', error);
        }
    }

    async getCustomMessages(): Promise<CustomMessage[]> {
        try {
            const session = await this.mongoCollection.findOne(
                { sessionId: this.getSessionId() },
                { projection: { messages: 1 } }
            );

            return session?.messages || [];
        } catch (error) {
            console.warn('Failed to get custom messages:', error);
            return [];
        }
    }

    async getSessionMetadata(): Promise<ExtendedChatMetadata | null> {
        try {
            const session = await this.mongoCollection.findOne(
                { sessionId: this.getSessionId() },
                { projection: { user_id: 1, collection_id: 1, title: 1, CreatedAt: 1, UpdatedAt: 1 } }
            );

            if (session) {
                return {
                    user_id: session.user_id,
                    collection_id: session.collection_id,
                    title: session.title
                };
            }
            return null;
        } catch (error) {
            console.warn('Failed to get session metadata:', error);
            return null;
        }
    }
}


export class ChatHistoryService implements IChatHistoryService {
    private chatMemoryCollection: any;
    private summariesCollection: any;
    private readonly shortTermLimit: number = 10;
    private readonly summaryWordLimit: number = 50;

    constructor(
        private mongoClient: MongoClient,
        private model: ChatOpenAI
    ) {
        this.chatMemoryCollection = this.mongoClient.db("ai_assistant").collection("chat_memory");
        this.summariesCollection = this.mongoClient.db("ai_assistant").collection("chat_summaries");
    }

    async getChatHistory(
        userId: string,
        sessionId: string,
        metadata?: ExtendedChatMetadata
    ): Promise<ExtendedMongoDBChatHistory> {
        return new ExtendedMongoDBChatHistory({
            collection: this.chatMemoryCollection,
            sessionId: sessionId,
            metadata: {
                user_id: userId,
                ...metadata
            }
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

    async saveConversation(
        chatHistory: ExtendedMongoDBChatHistory,
        userQuery: string,
        agentResponse: string,
        sessionId: string,
        docId?: string
    ): Promise<void> {
        try {
            // Only set title from first message
            await chatHistory.setTitleFromMessage(userQuery);

            if (docId) {
                chatHistory.updateMetadata({ doc_id: docId });
            }

            await chatHistory.addMessage(new HumanMessage(userQuery));
            await chatHistory.addMessage(new AIMessage(agentResponse));

            const allMessages = await chatHistory.getMessages();
            await this.checkAndCreateSummary(allMessages, sessionId);
        } catch (error) {
            console.error('Error saving conversation:', error);
            throw error;
        }
    }

    async cleanupDuplicateEntries(): Promise<void> {
        try {
            await this.chatMemoryCollection.deleteMany({
                $or: [
                    { SessionId: { $exists: true } },
                    { History: { $exists: true } },
                    { sessionId: { $exists: false } }
                ]
            });

            console.log('Cleaned up duplicate chat history entries');
        } catch (error) {
            console.error('Error cleaning up duplicate entries:', error);
        }
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

    async getUserConversations(userId: string, limit: number = 20): Promise<ConversationListItem[]> {
        try {
            const conversations = await this.chatMemoryCollection
                .find(
                    {
                        user_id: userId,
                        sessionId: { $exists: true }
                    },
                    {
                        projection: {
                            sessionId: 1,
                            title: 1,
                            collection_id: 1,
                            messages: 1,
                            UpdatedAt: 1,
                            CreatedAt: 1
                        }
                    }
                )
                .sort({ UpdatedAt: -1, CreatedAt: -1 })
                .limit(limit)
                .toArray();

            return conversations.map((conv: { sessionId: any; title: any; messages: string | any[]; UpdatedAt: any; CreatedAt: any; collection_id: any; }) => ({
                sessionId: conv.sessionId,
                title: conv.title || 'Untitled Conversation',
                messageCount: conv.messages?.length || 0,
                lastActivity: conv.UpdatedAt || conv.CreatedAt,
                collections: conv.collection_id || []
            }));
        } catch (error) {
            console.error('Error getting user conversations:', error);
            return [];
        }
    }

    async deleteConversation(sessionId: string, userId: string): Promise<boolean> {
        try {
            const result = await this.chatMemoryCollection.deleteOne({
                sessionId: sessionId,
                user_id: userId
            });

            return result.deletedCount > 0;
        } catch (error) {
            console.error('Error deleting conversation:', error);
            return false;
        }
    }

    async updateConversationTitle(sessionId: string, userId: string, newTitle: string): Promise<boolean> {
        try {
            const result = await this.chatMemoryCollection.updateOne(
                { sessionId: sessionId, user_id: userId },
                {
                    $set: {
                        title: newTitle,
                        UpdatedAt: new Date()
                    }
                }
            );

            return result.modifiedCount > 0;
        } catch (error) {
            console.error('Error updating conversation title:', error);
            return false;
        }
    }
}