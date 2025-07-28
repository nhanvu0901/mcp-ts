import { FastifyRequest, FastifyReply } from 'fastify';
import { HumanMessage } from '@langchain/core/messages';
import { AskAgentBody, AskAgentResponse, AgentToolInput } from '../types/ask.agent.types';
import { ChatHistoryService } from '../services';
import { AgentUtils } from '../utils';

export class AskAgentController {
    public static async askAgent(
        request: FastifyRequest<{ Body: AskAgentBody }>,
        reply: FastifyReply
    ): Promise<AskAgentResponse> {
        try {
            const { query, user_id: userId, collection_id: collectionId, doc_id: docId } = request.body;

            AgentUtils.validateRequest(query, userId, collectionId);

            const isDocumentSpecific = !!docId;
            const queryType = isDocumentSpecific ? 'document_specific' : 'general';

            const { aiResponse, ragResponse } = await AskAgentController.processAgentQuestion(
                request,
                query,
                userId,
                collectionId, // can be string or string[]
                docId
            );

            const sourceReferences = AgentUtils.extractSourceReferences(aiResponse, ragResponse);

            return reply.send({
                success: true,
                response: aiResponse,
                user_id: userId,
                collection_id: collectionId,
                timestamp: new Date().toISOString(),
                query_type: queryType,
                source_references: sourceReferences,
                sources_count: sourceReferences.length
            });
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
            const statusCode = errorMessage.includes('required') ? 400 : 500;

            request.log.error({
                error: errorMessage,
                stack: error instanceof Error ? error.stack : undefined
            }, 'Error processing agent question');

            return reply.status(statusCode).send({
                success: false,
                error: errorMessage
            });
        }
    }

    private static async checkDocumentsExist(
        mongoClient: any,
        userId: string,
        collectionIds: string[]
    ): Promise<boolean> {
        try {
            const db = mongoClient.db("ai_assistant");
            const collection = db.collection("documents");

            const query: any = {
                user_id: userId
            };

            // If collection_ids are provided, filter by them
            if (collectionIds.length > 0) {
                query.collection_id = { $in: collectionIds };
            }

            // Check if at least one document exists
            const documentExists = await collection.findOne(query, { projection: { _id: 1 } });

            return documentExists !== null;
        } catch (error) {
            console.warn('Failed to check document existence via MongoDB, assuming documents exist:', error);
            return true; // Default to true to maintain current behavior on error
        }
    }

    private static async processAgentQuestion(
        request: FastifyRequest,
        query: string,
        userId: string,
        collectionId: string | string[],
        docId?: string
    ): Promise<{ aiResponse: string; ragResponse: string | null }> {
        try {
            const { agent, mongoClient, model } = request.server;

            if (!agent || !mongoClient || !model) {
                throw new Error('Required services not initialized on server instance');
            }

            // Always treat collectionId as an array
            const collectionIds: string[] = Array.isArray(collectionId) ? collectionId : [collectionId];
            const sessionCollectionId = collectionIds.join(',');
            const sessionId = `${userId}_${sessionCollectionId}`;
            const chatHistoryService = new ChatHistoryService(mongoClient, model);
            const chatHistory = await chatHistoryService.getChatHistory(userId, sessionCollectionId);

            const allMessages = await chatHistory.getMessages();
            const contextMessages = await chatHistoryService.buildContextMessages(allMessages, sessionId);

            let userMessage: string;
            let hasDocumentContext = false;

            if (docId) {
                // Document-specific query - always has document context
                hasDocumentContext = true;
                userMessage = `User ID: ${userId}, Collection ID: ${sessionCollectionId}, Document ID: ${docId}, Has Document Context: true\n\nDocument-specific query: ${query}`;
            } else {
                // Check if collections have documents
                hasDocumentContext = await this.checkDocumentsExist(mongoClient, userId, collectionIds);

                if (hasDocumentContext) {
                    userMessage = `User ID: ${userId}, Collection ID: ${sessionCollectionId}, Has Document Context: true\n\nGeneral query: ${query}`;
                } else {
                    userMessage = `User ID: ${userId}, Collection ID: ${sessionCollectionId}, Has Document Context: false\n\nGeneral query: ${query}`;
                }
            }

            const messages = [
                ...contextMessages,
                new HumanMessage(userMessage)
            ];

            // Pass structured tool input to the agent, always as array
            const toolInput: AgentToolInput = {
                query,
                user_id: userId,
                collection_id: collectionIds,
                has_document_context: hasDocumentContext
            };
            if (docId) {
                toolInput.doc_id = docId;
            }

            const agentResponse = await agent.invoke({ messages, toolInput });
            const { aiResponse, ragResponse } = AgentUtils.extractResponseContent(agentResponse);

            await chatHistoryService.saveConversation(chatHistory, query, aiResponse, sessionId);

            return { aiResponse, ragResponse };

        } catch (error) {
            request.log.error({
                error: error instanceof Error ? error.message : String(error),
                userId,
                collectionId,
                docId
            }, 'Agent processing failed');
            throw new Error(`Agent processing failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
}