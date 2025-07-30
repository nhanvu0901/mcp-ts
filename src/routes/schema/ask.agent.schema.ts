export const AskAgentSchema = {
    tags: ["Ask Agent"],
    summary: "Ask the AI agent a question about documents or perform direct intent-based actions",
    description: "This endpoint supports two distinct modes of operation:\n\n" +
        "1. Query-based Mode (Traditional):\n" +
        "Submit natural language queries to the AI agent for intelligent document analysis, Q&A, and contextual responses.\n\n" +
        "2. Intent-based Mode (Direct Actions):\n" +
        "Execute specific, deterministic actions without AI interpretation.\n\n" +
        "Available Intent Types:\n\n" +
        "• summarise - Requires: doc_id\n" +
        "• translate - Requires: doc_id, target_language\n" +
        "• search - Requires: collection_id\n\n" +
        "Session Management:\n" +
        "- session_id is optional; if not provided, one will be auto-generated\n" +
        "- session_id is always returned in the response\n" +
        "- collection_id is optional; some intents may require it",
    security: [{ bearerAuth: [] }],
    body: {
        type: "object",
        required: ["user_id"],
        properties: {
            query: {
                type: "string",
                description: "The query to search for in documents. Required when intent is not provided.",
                minLength: 1,
                maxLength: 2000
            },
            user_id: {
                type: "string",
                description: "User identifier"
            },
            session_id: {
                type: "string",
                description: "Optional session identifier. Auto-generated if not provided."
            },
            collection_id: {
                anyOf: [
                    {type: "string"},
                    {type: "array", items: {type: "string"}, minItems: 1}
                ],
                description: "Optional collection identifier(s). Required for search intent."
            },
            doc_id: {
                type: "string",
                description: "Optional document ID. Required for summarise and translate intents."
            },
            intent: {
                type: "object",
                description: "Optional intent object for direct action routing.",
                properties: {
                    intent: {
                        type: "string",
                        enum: ["summarise", "translate", "search"],
                        description: "The type of action to perform"
                    },
                    level: {
                        type: "string",
                        enum: ["concise", "medium", "detailed"],
                        description: "Detail level for summarization (summarise intent only)"
                    },
                    word_count: {
                        type: "number",
                        minimum: 10,
                        maximum: 2000,
                        description: "Target word count for summarization (summarise intent only)"
                    },
                    target_language: {
                        type: "string",
                        description: "Target language for translation (translate intent only)"
                    },
                    limit: {
                        type: "number",
                        minimum: 1,
                        maximum: 20,
                        description: "Maximum search results (search intent only)"
                    }
                },
                required: ["intent"],
                additionalProperties: false
            }
        },
        anyOf: [
            {required: ["query"]},
            {required: ["intent"]}
        ]
    },
    response: {
        200: {
            description: "Agent response generated successfully",
            type: "object",
            properties: {
                success: {type: "boolean"},
                response: {type: "string"},
                user_id: {type: "string"},
                session_id: {type: "string"},
                collection_id: {
                    anyOf: [
                        {type: "string"},
                        {type: "array", items: {type: "string"}}
                    ]
                },
                timestamp: {type: "string"},
                query_type: {type: "string", enum: ["document_specific", "general", "intent_based"]},
                intent_type: {type: "string"},
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
                        required: ["document_name", "source_reference", "reference_type"]
                    }
                },
                sources_count: {type: "number"}
            }
        }
    }
};