export class AgentUtils {
    static extractResponseContent(agentResponse: any): string {
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
    }

    static validateRequest(query: string, userId: string, collectionId: string): void {
        if (!query?.trim()) {
            throw new Error('Query is required and cannot be empty');
        }

        if (!userId) {
            throw new Error('user_id is required');
        }

        if (!collectionId) {
            throw new Error('collection_id is required');
        }
    }
}