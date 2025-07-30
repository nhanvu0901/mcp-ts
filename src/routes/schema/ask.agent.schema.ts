export const AskAgentSchema = {
    tags: ["Ask Agent"],
    summary: "Ask the AI agent a question about documents or perform direct intent-based actions (summarization, translation, search)",
    description: "This endpoint supports two distinct modes of operation:\n\n" +
        "1. Query-based Mode (Traditional):\n" +
        "Submit natural language queries to the AI agent for intelligent document analysis, Q&A, and contextual responses. The agent will interpret your query and use appropriate tools to search, analyze, and respond based on your document collection.\n\n" +
        "2. Intent-based Mode (Direct Actions):\n" +
        "Execute specific, deterministic actions without AI interpretation. Perfect for programmatic integrations, UI actions, and scenarios requiring predictable behavior.\n\n" +
        "Available Intent Types:\n\n" +
        "• summarise - Generate document summaries with control over detail level or target word count\n" +
        "  - Requires: doc_id (specific document to summarize)\n" +
        "  - Options: level ('concise', 'medium', 'detailed') OR word_count (10-2000 words)\n\n" +
        "• translate - Translate documents to target languages\n" +
        "  - Requires: doc_id (document to translate), target_language (e.g., 'en', 'de', 'fr', 'es')\n\n" +
        "• search - Search across document collections with result limiting\n" +
        "  - Optional: limit (1-20 results), can work with or without query parameter\n\n" +
        "Request Priority:\n" +
        "When both 'query' and 'intent' are provided, intent takes precedence and the request will be processed as an intent-based action.\n\n" +
        "Collection Support:\n" +
        "Both modes support single collections (string) or multi-collection search (array of collection IDs).\n\n" +
        "Use Cases:\n" +
        "- Traditional: 'What are the key findings in our Q4 report?'\n" +
        "- Intent-based: {\"intent\": \"summarise\", \"level\": \"medium\"}",
    security: [
        {
            bearerAuth: []
        }
    ],
    body: {
        type: "object",
        required: ["user_id"],
        properties: {
            query: {
                type: "string",
                description: "The query to search for in documents or question. Required when intent is not provided.",
                minLength: 1,
                maxLength: 2000
            },
            user_id: {
                type: "string",
                description: "User identifier"
            },
            session_id: {
                type: "string",
                description: "Optional session identifier. If not provided, a new session will be created."
            },
            collection_id: {
                anyOf: [
                    {type: "string"},
                    {type: "array", items: {type: "string"}, minItems: 1}
                ],
                description: "Optional collection identifier(s) to search within. Can be a string or an array of strings."
            },
            doc_id: {
                type: "string",
                description: "Optional document ID for document-specific queries or intent actions"
            },
            intent: {
                type: "object",
                description: "Optional intent object for direct action routing. Takes precedence over query parameter.",
                properties: {
                    intent: {
                        type: "string",
                        enum: ["summarise", "translate", "search"],
                        description: "The type of action to perform"
                    },
                    level: {
                        type: "string",
                        enum: ["concise", "medium", "detailed"],
                        description: "Detail level for summarization (only for 'summarise' intent)"
                    },
                    word_count: {
                        type: "number",
                        minimum: 10,
                        maximum: 2000,
                        description: "Target word count for summarization (only for 'summarise' intent)"
                    },
                    target_language: {
                        type: "string",
                        description: "Target language for translation (only for 'translate' intent)"
                    },
                    limit: {
                        type: "number",
                        minimum: 1,
                        maximum: 20,
                        description: "Maximum number of search results (only for 'search' intent)"
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
                        required: ["document_name", "source_reference", "reference_type", "text_content"]
                    }
                },
                sources_count: {type: "number"}
            }
        }
    }
};