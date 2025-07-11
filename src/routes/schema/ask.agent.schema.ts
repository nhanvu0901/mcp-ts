export const AskAgentSchema = {
    tags: ["Ask Agent"],
    summary: "Ask the AI agent a question about documents in a specific collection",
    description: "Submit a query to the AI agent which will search through documents in the specified collection",
    security: [
        {
            bearerAuth: []
        }
    ],
    body: {
        type: "object",
        required: ["query", "user_id", "collection_id"],
        properties: {
            query: {
                type: "string",
                description: "The query to search for in documents",
                minLength: 1,
                maxLength: 2000
            },
            user_id: {
                type: "string",
                description: "User identifier"
            },
            collection_id: {
                type: "string",
                description: "Collection identifier to search within"
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
                collection_id: { type: "string" },
                timestamp: { type: "string" }
            }
        },
        400: {
            description: "Bad request - invalid query or missing parameters",
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