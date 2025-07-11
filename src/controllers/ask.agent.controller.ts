import { FastifyRequest, FastifyReply } from 'fastify';
import { AskAgentBody, AskAgentResponse } from '../types/ask.agent.types';

export class AskAgentController {
    public static async askAgent(
        request: FastifyRequest<{ Body: AskAgentBody }>,
        reply: FastifyReply
    ): Promise<AskAgentResponse> {
        try {
            const { question, user_id: userId, session_id = 'default' } = request.body;

            if (!question?.trim()) {
                return reply.status(400).send({
                    success: false,
                    error: 'Question is required and cannot be empty'
                });
            }

            if (!userId) {
                return reply.status(400).send({
                    success: false,
                    error: 'user_id is required'
                });
            }

            const agentResponse = await AskAgentController.processAgentQuestion(
                request,
                question,
                userId,
                session_id
            );

            return reply.send({
                success: true,
                response: agentResponse,
                user_id: userId,
                session_id,
                timestamp: new Date().toISOString()
            });

        } catch (error) {
            request.log.error({
                error: error instanceof Error ? error.message : String(error),
                stack: error instanceof Error ? error.stack : undefined
            }, 'Error processing agent question');

            return reply.status(500).send({
                success: false,
                error: error instanceof Error ? error.message : 'Unknown error occurred'
            });
        }
    }

    private static async processAgentQuestion(
        request: FastifyRequest,
        question: string,
        userId: string,
        sessionId: string
    ): Promise<string> {
        try {
            const agent = request.server.agent;
            if (!agent) {
                throw new Error('Agent not initialized on server instance');
            }

            const agentInput = {
                messages: [
                    {
                        role: "user" as const,
                        content: `User ID: ${userId},Qdrant , Session: ${sessionId}\n\nQuestion: ${question}`
                    }
                ]
            };

            const agentResponse = await agent.invoke(agentInput);

            if (!agentResponse?.messages?.length) {
                throw new Error('Agent returned invalid response');
            }

            const lastMessage = agentResponse.messages[agentResponse.messages.length - 1];

            if (!lastMessage?.content) {
                throw new Error('Agent response missing content');
            }

            return typeof lastMessage.content === 'string'
                ? lastMessage.content
                : JSON.stringify(lastMessage.content);

        } catch (error) {
            request.log.error({
                error: error instanceof Error ? error.message : String(error),
                userId,
                sessionId
            }, 'Agent processing failed');
            throw new Error(`Agent processing failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
}