import { FastifyRequest, FastifyReply } from 'fastify';
import { HumanMessage } from '@langchain/core/messages';
import { AskAgentBody, AskAgentResponse, AgentToolInput } from '../types/ask.agent.types';
import { IntentRequest} from "../types/intent.types";
import { ChatHistoryService } from '../services';
import { AgentUtils } from '../utils';
import { IntentUtils } from '../utils/intent.utils';

export class AskAgentController {
    public static async askAgent(
        request: FastifyRequest<{ Body: AskAgentBody }>,
        reply: FastifyReply
    ): Promise<AskAgentResponse> {
        try {
            const { query, user_id: userId, collection_id: collectionId, doc_id: docId, intent } = request.body;

            if (!query && !intent) {
                throw new Error('Either query or intent parameter is required');
            }

            if (intent) {
                IntentUtils.validateIntent(intent, docId);
                if (!userId) throw new Error('user_id is required');
                if (!collectionId) throw new Error('collection_id is required');
            } else {
                AgentUtils.validateRequest(query, userId, collectionId);
            }

            let queryType: 'document_specific' | 'general' | 'intent_based';
            let intentType: string | undefined;
            let aiResponse: string;
            let ragResponse: string | null = null;

            if (intent) {
                queryType = 'intent_based';
                intentType = intent.intent;

                const result = await AskAgentController.processIntentRequest(
                    request,
                    intent,
                    userId,
                    collectionId,
                    docId,
                    query
                );

                aiResponse = result.aiResponse;
                ragResponse = result.ragResponse;
            } else {
                const isDocumentSpecific = !!docId;
                queryType = isDocumentSpecific ? 'document_specific' : 'general';

                const result = await AskAgentController.processAgentQuestion(
                    request,
                    query,
                    userId,
                    collectionId,
                    docId
                );

                aiResponse = result.aiResponse;
                ragResponse = result.ragResponse;
            }

            const sourceReferences = AgentUtils.extractSourceReferences(aiResponse, ragResponse);

            return reply.send({
                success: true,
                response: aiResponse,
                user_id: userId,
                collection_id: collectionId,
                timestamp: new Date().toISOString(),
                query_type: queryType,
                intent_type: intentType,
                source_references: sourceReferences,
                sources_count: sourceReferences.length
            });
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
            const statusCode = errorMessage.includes('required') || errorMessage.includes('Invalid') ? 400 : 500;

            request.log.error({
                error: errorMessage,
                stack: error instanceof Error ? error.stack : undefined,
                intent: request.body.intent
            }, 'Error processing agent question');

            return reply.status(statusCode).send({
                success: false,
                error: errorMessage
            });
        }
    }

    private static async processIntentRequest(
        request: FastifyRequest,
        intent: IntentRequest,
        userId: string,
        collectionId: string | string[],
        docId?: string,
        fallbackQuery?: string
    ): Promise<{ aiResponse: string; ragResponse: string | null }> {
        try {
            const { mcpClient } = request.server;

            if (!mcpClient) {
                throw new Error('MCP client not initialized on server instance');
            }

            request.log.info({
                intent: intent.intent,
                userId,
                collectionId,
                docId,
                intentParams: { ...intent, intent: undefined }
            }, 'Processing intent-based request');

            const result = await IntentUtils.processIntent(
                mcpClient,
                intent,
                userId,
                collectionId,
                docId,
                fallbackQuery
            );

            return {
                aiResponse: result.response,
                ragResponse: result.ragResponse
            };

        } catch (error) {
            request.log.error({
                error: error instanceof Error ? error.message : String(error),
                intent: intent.intent,
                userId,
                collectionId,
                docId
            }, 'Intent processing failed');

            throw new Error(`Intent processing failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    private static async checkDocumentsExist(
        mongoClient: any,
        userId: string,
        collectionIds: string[],
        docId?: string
    ): Promise<boolean> {
        try {
            const db = mongoClient.db("ai_assistant");
            const collection = db.collection("documents");
            if (docId) {
                const documentExists = await collection.findOne(
                    {
                        _id: docId,
                        user_id: userId
                    },
                    {projection: {_id: 1}}
                );
                return documentExists !== null;
            } else {
                const query: any = {
                    user_id: userId
                };
                if (collectionIds.length > 0) {
                    query.collection_id = {$in: collectionIds};
                }
                const documentExists = await collection.findOne(query, {projection: {_id: 1}});

                return documentExists !== null;
            }
        } catch (error) {
            console.warn('Failed to check document existence via MongoDB, assuming documents exist:', error);
            return false;
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
                hasDocumentContext = await this.checkDocumentsExist(mongoClient, userId, collectionIds, docId);

                if (hasDocumentContext) {
                    userMessage = `User ID: ${userId}, Collection ID: ${sessionCollectionId}, Document ID: ${docId}, Has Document Context: true\n\nDocument-specific query: ${query}`;
                } else {
                    userMessage = `User ID: ${userId}, Collection ID: ${sessionCollectionId}, Document ID: ${docId}, Has Document Context: false\n\nDocument-specific query: ${query}`;
                }
            } else {
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

            await chatHistoryService.saveConversation(chatHistory, query, aiResponse, sessionId, docId);

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