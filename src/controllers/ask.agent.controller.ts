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

            request.log.info({
                question: question.substring(0, 100),
                userId,
                session_id
            }, 'Processing agent question');

            const agentResponse = await AskAgentController.processAgentQuestion(
                request,
                question,
                userId,
                session_id
            );

            return reply.send({
                success: true,
                response: agentResponse,
                userId,
                session_id,
                timestamp: new Date().toISOString()
            });

        } catch (error) {
            request.log.error('Error processing agent question:', error);
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
                throw new Error('Agent not initialized');
            }

            const context = `User ID: ${userId}, Session: ${sessionId}`;
            const fullPrompt = `${context}\n\nUser Question: ${question}`;

            const agentResponse = await agent.invoke({
                messages: [
                    {
                        role: "user",
                        content: fullPrompt
                    }
                ]
            });

            return agentResponse.messages[agentResponse.messages.length - 1].content;

        } catch (error) {
            request.log.error('Agent processing failed:', error);
            throw new Error(`Agent processing failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }
}