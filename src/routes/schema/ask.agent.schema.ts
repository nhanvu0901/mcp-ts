export const AskAgentSchema = {
    tags: ["Ask Agent"],
    summary: "Ask the AI agent a question",
    description: "Submit a question to the AI agent which will use available MCP tools to provide an answer",
    security: [
        {
            bearerAuth: []
        }
    ],
    body: {
        type: "object",
        required: ["question", "user_id"],
        properties: {
            question: {
                type: "string",
                description: "The question to ask the agent",
                minLength: 1,
                maxLength: 2000
            },
            user_id: {
                type: "string",
                description: "User identifier"
            },
            session_id: {
                type: "string",
                description: "Session identifier",
                default: "default"
            }
        }
    },
    response: {
        200: {
            description: "Agent response generated successfully",
            type: "object",
            properties: {
                success: { type: "boolean" },
                response: { type: "string" },
                user_id: { type: "string" },
                session_id: { type: "string" },
                timestamp: { type: "string" }
            }
        },
        400: {
            description: "Bad request - invalid question or missing parameters",
            type: "object",
            properties: {
                error: { type: "string" },
                success: { type: "boolean" }
            }
        },
        500: {
            description: "Internal server error",
            type: "object",
            properties: {
                error: { type: "string" },
                success: { type: "boolean" }
            }
        }
    }
};