import { FastifyRequest, FastifyReply } from 'fastify';
import { HumanMessage } from '@langchain/core/messages';
import { AskAgentBody, AskAgentResponse } from '../types/ask.agent.types';
import { ChatHistoryService } from '../services';
import { AgentUtils } from '../utils';

export class AskAgentController {
    public static async askAgent(
        request: FastifyRequest<{ Body: AskAgentBody }>,
        reply: FastifyReply
    ): Promise<AskAgentResponse> {
        try {
            const { query, user_id: userId, collection_id: collectionId } = request.body;

            AgentUtils.validateRequest(query, userId, collectionId);

            const agentResponse = await AskAgentController.processAgentQuestion(
                request,
                query,
                userId,
                collectionId
            );

            const sourceReferences = AgentUtils.extractSourceReferences(agentResponse);


            return reply.send({
                success: true,
                response: agentResponse,
                user_id: userId,
                collection_id: collectionId,
                timestamp: new Date().toISOString(),
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

    private static async processAgentQuestion(
        request: FastifyRequest,
        query: string,
        userId: string,
        collectionId: string
    ): Promise<string> {
        try {
            const { agent, mongoClient, model } = request.server;

            if (!agent || !mongoClient || !model) {
                throw new Error('Required services not initialized on server instance');
            }

            const sessionId = `${userId}_${collectionId}`;
            const chatHistoryService = new ChatHistoryService(mongoClient, model);
            const chatHistory = await chatHistoryService.getChatHistory(userId, collectionId);

            const allMessages = await chatHistory.getMessages();
            const contextMessages = await chatHistoryService.buildContextMessages(allMessages, sessionId);

            const messages = [
                ...contextMessages,
                new HumanMessage(`User ID: ${userId}, Collection ID: ${collectionId}\n\nQuery: ${query}`)
            ];

            const agentResponse = await agent.invoke({ messages });
            const responseContent = AgentUtils.extractResponseContent(agentResponse);

            await chatHistoryService.saveConversation(chatHistory, query, responseContent, sessionId);

            return responseContent;

        } catch (error) {
            request.log.error({
                error: error instanceof Error ? error.message : String(error),
                userId,
                collectionId
            }, 'Agent processing failed');
            throw new Error(`Agent processing failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
}