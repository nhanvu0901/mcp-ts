export const AskAgentSchema = {
    tags: ["Ask Agent"],
    summary: "Ask the AI agent a question about documents in a specific collection",
    description: "Submit a query to the AI agent which will search through documents in the specified collection and return source references",
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
            description: "Agent response generated successfully with source references",
            type: "object",
            properties: {
                success: {type: "boolean"},
                response: {type: "string"},
                user_id: {type: "string"},
                collection_id: {type: "string"},
                timestamp: {type: "string"},
                source_references: {
                    type: "array",
                    items: {
                        type: "object",
                        properties: {
                            document_name: {type: "string"},
                            page_number: {type: "number"},
                            chunk_id: {type: "number"},
                            source_reference: {type: "string"},
                            reference_type: {type: "string", enum: ["page", "chunk"]},
                            text_content: {type: "string"},
                        },
                        required: ["document_name", "source_reference", "reference_type", "text_content"]
                    }
                },
                sources_count: {type: "number"}
            }
        },
        400: {
            description: "Bad request - invalid query or missing parameters",
            type: "object",
            properties: {
                error: {type: "string"},
                success: {type: "boolean"}
            }
        },
        500: {
            description: "Internal server error",
            type: "object",
            properties: {
                error: {type: "string"},
                success: {type: "boolean"}
            }
        }
    }
};