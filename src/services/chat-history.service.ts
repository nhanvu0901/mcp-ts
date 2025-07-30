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
    private initializationPromise: Promise<void>;
    private sessionIdField: string;

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
        this.sessionIdField = 'SessionId';
        this.initializationPromise = this.initializeSession(fields.sessionId);
    }

    private getSessionId(): string {
        return (this as any).sessionId;
    }

    private getSessionQuery(sessionId: string): any {
        return {
            [this.sessionIdField]: sessionId,
            user_id: this.metadata.user_id
        };
    }

    private async initializeSession(sessionId: string): Promise<void> {
        try {
            if (!sessionId || sessionId === 'null' || sessionId === 'undefined') {
                throw new Error('Invalid sessionId provided');
            }

            if (!this.metadata.user_id) {
                throw new Error('user_id is required in metadata');
            }

            const query = this.getSessionQuery(sessionId);
            const existingSession = await this.mongoCollection.findOne(query);

            if (!existingSession) {
                const sessionDoc = {
                    [this.sessionIdField]: sessionId,
                    user_id: this.metadata.user_id,
                    collection_id: this.metadata.collection_id || [],
                    title: this.metadata.title || null,
                    messages: [],
                    CreatedAt: new Date(),
                    UpdatedAt: new Date()
                };

                await this.mongoCollection.insertOne(sessionDoc);
                console.log(`Created new session: ${sessionId} for user: ${this.metadata.user_id}`);
            } else {
                console.log(`Found existing session: ${sessionId} for user: ${this.metadata.user_id}`);
            }
        } catch (error) {
            console.error('Failed to initialize session:', error);


            throw error;

        }
    }

    private async handleDuplicateKeyError(sessionId: string): Promise<void> {
        console.log('Handling duplicate key error...');

        try {
            // Only delete sessions for this specific user and sessionId combination
            await this.mongoCollection.deleteMany({
                [this.sessionIdField]: sessionId,
                user_id: this.metadata.user_id
            });

            const sessionDoc = {
                [this.sessionIdField]: sessionId,
                user_id: this.metadata.user_id,
                collection_id: this.metadata.collection_id || [],
                title: this.metadata.title || null,
                messages: [],
                CreatedAt: new Date(),
                UpdatedAt: new Date()
            };

            await this.mongoCollection.insertOne(sessionDoc);
            console.log(`Successfully created session after cleanup: ${sessionId} for user: ${this.metadata.user_id}`);
        } catch (retryError) {
            console.error('Retry after cleanup failed:', retryError);
            throw retryError;
        }
    }

    override async addMessage(message: BaseMessage): Promise<void> {
        await this.initializationPromise;

        try {
            const sessionId = this.getSessionId();
            if (!sessionId || sessionId === 'null') {
                throw new Error('Invalid sessionId for addMessage');
            }

            if (!this.metadata.user_id) {
                throw new Error('user_id is required for addMessage');
            }

            const customMessage = this.convertToCustomMessage(message);

            const updateFields: any = {
                UpdatedAt: new Date(),
                user_id: this.metadata.user_id,
                collection_id: this.metadata.collection_id || [],
            };

            if (this.metadata.title) {
                updateFields.title = this.metadata.title;
            }

            const query = this.getSessionQuery(sessionId);
            const result = await this.mongoCollection.updateOne(
                query,
                {
                    $set: updateFields,
                    $push: { messages: customMessage as any}
                },
                { upsert: false }
            );

            if (result.matchedCount === 0) {
                throw new Error(`Session not found: ${sessionId} for user: ${this.metadata.user_id}`);
            }

            console.log(`Added message to session: ${sessionId} for user: ${this.metadata.user_id}`);
        } catch (error) {
            console.error('Error adding custom message:', error);
            throw error;
        }
    }

    override async getMessages(): Promise<BaseMessage[]> {
        await this.initializationPromise;

        try {
            const sessionId = this.getSessionId();
            if (!sessionId || sessionId === 'null') {
                console.log('No valid sessionId, returning empty messages');
                return [];
            }

            if (!this.metadata.user_id) {
                console.log('No user_id in metadata, returning empty messages');
                return [];
            }

            const query = this.getSessionQuery(sessionId);
            console.log(`Getting messages for query:`, query);

            const session = await this.mongoCollection.findOne(
                query,
                { projection: { messages: 1, SessionId: 1, user_id: 1 } }
            );

            if (!session) {
                console.log(`No session found for sessionId: ${sessionId}, user_id: ${this.metadata.user_id}`);
                return [];
            }

            if (!session.messages || session.messages.length === 0) {
                console.log(`Session found but no messages for sessionId: ${sessionId}, user_id: ${this.metadata.user_id}`);
                return [];
            }

            console.log(`Found ${session.messages.length} messages for sessionId: ${sessionId}, user_id: ${this.metadata.user_id}`);

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
            console.error('Failed to get messages:', error);
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
        await this.initializationPromise;

        try {
            const sessionId = this.getSessionId();
            if (!sessionId || sessionId === 'null' || !this.metadata.user_id) {
                return;
            }

            const query = this.getSessionQuery(sessionId);
            const existingSession = await this.mongoCollection.findOne(
                query,
                { projection: { title: 1, messages: 1 } }
            );

            if (!existingSession?.title && (!existingSession?.messages || existingSession.messages.length === 0)) {
                const cleanMessage = message
                    .replace(/^(User ID:|Collection ID:|Document ID:|Has Document Context:).*?\n\n/g, '')
                    .replace(/^(Document-specific query:|General query:|Collection-specific query:)\s*/i, '')
                    .trim();

                const title = cleanMessage.length > maxLength
                    ? cleanMessage.substring(0, maxLength).trim() + '...'
                    : cleanMessage.trim();

                if (title && title !== '...') {
                    this.metadata.title = title;

                    await this.mongoCollection.updateOne(
                        query,
                        {
                            $set: {
                                title: title,
                                UpdatedAt: new Date()
                            }
                        }
                    );

                    console.log(`Set title "${title}" for session: ${sessionId}, user: ${this.metadata.user_id}`);
                }
            }
        } catch (error) {
            console.warn('Failed to set title:', error);
        }
    }

    async getCustomMessages(): Promise<CustomMessage[]> {
        await this.initializationPromise;

        try {
            const sessionId = this.getSessionId();
            if (!sessionId || sessionId === 'null' || !this.metadata.user_id) {
                return [];
            }

            const query = this.getSessionQuery(sessionId);
            const session = await this.mongoCollection.findOne(
                query,
                { projection: { messages: 1 } }
            );

            return session?.messages || [];
        } catch (error) {
            console.warn('Failed to get custom messages:', error);
            return [];
        }
    }

    async getSessionMetadata(): Promise<ExtendedChatMetadata | null> {
        await this.initializationPromise;

        try {
            const sessionId = this.getSessionId();
            if (!sessionId || sessionId === 'null' || !this.metadata.user_id) {
                return null;
            }

            const query = this.getSessionQuery(sessionId);
            const session = await this.mongoCollection.findOne(
                query,
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
        if (!sessionId || sessionId === 'null' || sessionId === 'undefined') {
            throw new Error(`Invalid sessionId: ${sessionId}`);
        }

        if (!userId) {
            throw new Error('userId is required');
        }

        console.log(`Getting chat history for sessionId: ${sessionId}, userId: ${userId}`);

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
        console.log(`Building context messages for sessionId: ${sessionId}, total messages: ${allMessages.length}`);

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
        console.log(`Context messages built: ${contextMessages.length} total messages`);
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
            console.log(`Saving conversation for sessionId: ${sessionId}`);

            await chatHistory.setTitleFromMessage(userQuery);

            if (docId) {
                chatHistory.updateMetadata({ doc_id: docId });
            }

            await chatHistory.addMessage(new HumanMessage(userQuery));
            await chatHistory.addMessage(new AIMessage(agentResponse));

            const allMessages = await chatHistory.getMessages();
            await this.checkAndCreateSummary(allMessages, sessionId);

            console.log(`Conversation saved successfully for sessionId: ${sessionId}`);
        } catch (error) {
            console.error('Error saving conversation:', error);
            throw error;
        }
    }

    async cleanupDuplicateEntries(): Promise<void> {
        try {
            await this.chatMemoryCollection.deleteMany({
                $or: [
                    { SessionId: null },
                    { History: { $exists: true } }
                ]
            });
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
                        SessionId: { $exists: true, $ne: null }
                    },
                    {
                        projection: {
                            SessionId: 1,
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

            return conversations.map((conv: { SessionId: any; title: any; messages: string | any[]; UpdatedAt: any; CreatedAt: any; collection_id: any; }) => ({
                sessionId: conv.SessionId,
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
                SessionId: sessionId,
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
                { SessionId: sessionId, user_id: userId },
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