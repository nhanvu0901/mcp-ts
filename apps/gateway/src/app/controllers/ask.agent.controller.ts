import { FastifyRequest, FastifyReply } from "fastify";
import { HumanMessage } from "@langchain/core/messages";
import { AskAgentBody, AskAgentResponse, AgentToolInput } from "../types/ask.agent.types";
import { IntentRequest } from "../types/intent.types";
import { ChatHistoryService } from "../services";
import { AgentUtils } from "../utils";
import { IntentUtils } from "../utils/intent.utils";

export class AskAgentController {
    public static async askAgent(
        request: FastifyRequest<{ Body: AskAgentBody }>,
        reply: FastifyReply
    ): Promise<AskAgentResponse> {
        try {
            const {
                query,
                user_id: userId,
                collection_id: collectionId,
                doc_id: docId,
                intent,
                session_id: providedSessionId,
            } = request.body;

            if (!query && !intent) {
                throw new Error("Either query or intent parameter is required");
            }

            if (!userId) {
                throw new Error("user_id is required");
            }

            const sessionId =
                providedSessionId || AgentUtils.generateSessionId(userId, collectionId);

            if (intent) {
                IntentUtils.validateIntent(intent, docId, collectionId);

                const result = await AskAgentController.processIntentRequest(
                    request,
                    intent,
                    userId,
                    collectionId,
                    docId,
                    query,
                    sessionId
                );

                return reply.send({
                    success: true,
                    response: result.aiResponse,
                    user_id: userId,
                    session_id: sessionId,
                    collection_id: collectionId,
                    timestamp: new Date().toISOString(),
                    query_type: "intent_based",
                    intent_type: intent.intent,
                    source_references: AgentUtils.extractSourceReferences(
                        result.aiResponse,
                        result.ragResponse
                    ),
                    sources_count: AgentUtils.extractSourceReferences(
                        result.aiResponse,
                        result.ragResponse
                    ).length,
                });
            }

            AgentUtils.validateRequest(query as string, userId);

            const isDocumentSpecific = !!docId;
            const queryType = isDocumentSpecific ? "document_specific" : "general";

            const result = await AskAgentController.processAgentQuestion(
                request,
                query as string,
                userId,
                collectionId,
                docId,
                sessionId
            );

            const sourceReferences = AgentUtils.extractSourceReferences(
                result.aiResponse,
                result.ragResponse
            );

            return reply.send({
                success: true,
                response: result.aiResponse,
                user_id: userId,
                session_id: sessionId,
                collection_id: collectionId,
                timestamp: new Date().toISOString(),
                query_type: queryType,
                source_references: sourceReferences,
                sources_count: sourceReferences.length,
            });
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : "Unknown error occurred";
            const statusCode =
                errorMessage.includes("required") || errorMessage.includes("Invalid") ? 400 : 500;

            request.log.error(
                {
                    error: errorMessage,
                    stack: error instanceof Error ? error.stack : undefined,
                    intent: request.body.intent,
                },
                "Error processing agent request"
            );

            return reply.status(statusCode).send({
                success: false,
                error: errorMessage,
            });
        }
    }

    private static async processIntentRequest(
        request: FastifyRequest,
        intent: IntentRequest,
        userId: string,
        collectionId?: string | string[],
        docId?: string,
        fallbackQuery?: string,
        sessionId?: string
    ): Promise<{ aiResponse: string; ragResponse: string | null }> {
        try {
            const { mcpClient, mongoClient, model } = request.server;

            if (!mcpClient) {
                throw new Error("MCP client not initialized on server instance");
            }
            if (!mongoClient || !model) {
                throw new Error("Required services not initialized on server instance");
            }
            request.log.info(
                {
                    intent: intent.intent,
                    userId,
                    collectionId,
                    docId,
                    intentParams: { ...intent, intent: undefined },
                },
                "Processing intent-based request"
            );

            const result = await IntentUtils.processIntent(
                mcpClient,
                intent,
                userId,
                collectionId,
                docId,
                fallbackQuery
            );
            if (sessionId) {
                const chatHistoryService = new ChatHistoryService(mongoClient, model);
                const collectionIds: string[] = collectionId
                    ? Array.isArray(collectionId)
                        ? collectionId
                        : [collectionId]
                    : [];

                const chatHistory = await chatHistoryService.getChatHistory(userId, sessionId, {
                    user_id: userId,
                    collection_id: collectionIds,
                    doc_id: docId,
                });

                const intentQuery =
                    `Intent: ${intent.intent}` +
                    (intent.word_count ? ` (${intent.word_count} words)` : "") +
                    (intent.level ? ` (${intent.level} level)` : "") +
                    (intent.target_language ? ` (translate to ${intent.target_language})` : "") +
                    (docId ? ` for document ${docId}` : "");

                await chatHistoryService.saveConversation(
                    chatHistory,
                    intentQuery,
                    result.response,
                    sessionId,
                    docId
                );
            }
            return {
                aiResponse: result.response,
                ragResponse: result.ragResponse,
            };
        } catch (error) {
            request.log.error(
                {
                    error: error instanceof Error ? error.message : String(error),
                    intent: intent.intent,
                    userId,
                    collectionId,
                    docId,
                },
                "Intent processing failed"
            );

            throw new Error(
                `Intent processing failed: ${error instanceof Error ? error.message : String(error)}`
            );
        }
    }

    private static async checkDocumentsExist(
        mongoClient: any,
        userId: string,
        collectionIds?: string[],
        docId?: string
    ): Promise<boolean> {
        try {
            const db = mongoClient.db("ai_assistant");
            const collection = db.collection("documents");

            if (docId) {
                const documentExists = await collection.findOne(
                    {
                        _id: docId,
                        user_id: userId,
                    },
                    { projection: { _id: 1 } }
                );
                return documentExists !== null;
            } else {
                const query: any = {
                    user_id: userId,
                };

                if (collectionIds && collectionIds.length > 0) {
                    query.collection_id = { $in: collectionIds };
                }

                const documentExists = await collection.findOne(query, { projection: { _id: 1 } });
                return documentExists !== null;
            }
        } catch (error) {
            console.warn("Failed to check document existence via MongoDB:", error);
            return false;
        }
    }

    private static async processAgentQuestion(
        request: FastifyRequest,
        query: string,
        userId: string,
        collectionId?: string | string[],
        docId?: string,
        sessionId?: string
    ): Promise<{ aiResponse: string; ragResponse: string | null }> {
        try {
            const { agent, mongoClient, model } = request.server;

            if (!agent || !mongoClient || !model) {
                throw new Error("Required services not initialized on server instance");
            }

            const finalSessionId = sessionId || AgentUtils.generateSessionId(userId, collectionId);

            const chatHistoryService = new ChatHistoryService(mongoClient, model);

            const collectionIds: string[] = collectionId
                ? Array.isArray(collectionId)
                    ? collectionId
                    : [collectionId]
                : [];

            const chatHistory = await chatHistoryService.getChatHistory(userId, finalSessionId, {
                user_id: userId,
                collection_id: collectionIds,
                doc_id: docId,
            });

            const allMessages = await chatHistory.getMessages();
            const contextMessages = await chatHistoryService.buildContextMessages(
                allMessages,
                finalSessionId
            );

            let hasDocumentContext = false;

            if (collectionIds.length > 0 || docId) {
                hasDocumentContext = await this.checkDocumentsExist(
                    mongoClient,
                    userId,
                    collectionIds,
                    docId
                );
            }

            let userMessage: string;
            const collectionIdStr = collectionIds.length > 0 ? collectionIds.join(",") : "none";

            if (docId) {
                userMessage = `User ID: ${userId}, Collection ID: ${collectionIdStr}, Document ID: ${docId}, Has Document Context: ${hasDocumentContext}\n\nDocument-specific query: ${query}`;
            } else if (collectionIds.length > 0) {
                userMessage = `User ID: ${userId}, Collection ID: ${collectionIdStr}, Has Document Context: ${hasDocumentContext}\n\nCollection-specific query: ${query}`;
            } else {
                userMessage = `User ID: ${userId}, Collection ID: ${collectionIdStr}, Has Document Context: ${hasDocumentContext}\n\nGeneral query: ${query}`;
            }

            const messages = [...contextMessages, new HumanMessage(userMessage)];

            const toolInput: AgentToolInput = {
                query,
                user_id: userId,
                collection_id: collectionIds.length > 0 ? collectionIds : undefined,
                has_document_context: hasDocumentContext,
            };

            if (docId) {
                toolInput.doc_id = docId;
            }

            console.log("toolInput:", toolInput);

            const agentResponse = await agent.invoke({ messages, toolInput });
            const { aiResponse, ragResponse } = AgentUtils.extractResponseContent(agentResponse);

            await chatHistoryService.saveConversation(
                chatHistory,
                query,
                aiResponse,
                finalSessionId,
                docId
            );

            return { aiResponse, ragResponse };
        } catch (error) {
            request.log.error(
                {
                    error: error instanceof Error ? error.message : String(error),
                    userId,
                    collectionId,
                    docId,
                },
                "Agent processing failed"
            );
            throw new Error(
                `Agent processing failed: ${error instanceof Error ? error.message : String(error)}`
            );
        }
    }
}
