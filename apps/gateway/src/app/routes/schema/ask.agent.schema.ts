export const AskAgentSchema = {
    tags: ["Ask Agent"],
    summary:
        "Ask the AI agent a question about documents or perform direct intent-based actions (summarization, translation, search)",
    description:
        "This endpoint supports two distinct modes of operation:\n\n" +
        "1. Query-based Mode (Traditional):\n" +
        "Submit natural language queries to the AI agent for intelligent document analysis, Q&A, and contextual responses. The agent will interpret your query and use appropriate tools to search, analyze, and respond based on your document collection.\n\n" +
        "2. Intent-based Mode (Direct Actions):\n" +
        "Execute specific, deterministic actions without AI decision-making overhead. Direct tool invocation for predictable results.\n\n" +
        "Available Intent Types:\n\n" +
        "• summarise - Generate document summaries with precision control\n" +
        "  - Requires: doc_id (target document)\n" +
        "  - Options: level ('concise', 'medium', 'detailed') OR word_count (10-2000)\n" +
        "  - Tools: DocDBSummarizationService (summarize_by_word_count, summarize_by_detail_level)\n\n" +
        "• translate - Document translation with language targeting\n" +
        "  - Requires: doc_id (source document), target_language (ISO language code)\n" +
        "  - Tools: DocumentTranslationService (translate_document)\n\n" +
        "• search - Retrieve relevant documents from collections\n" +
        "  - Requires: collection_id (single string or array)\n" +
        "  - Options: limit (1-20 results, default: 5)\n" +
        "  - Tools: RAGService (retrieve)\n" +
        "  - Returns: Ranked document excerpts with relevance scoring\n\n" +
        "Processing Priority:\n" +
        "Intent-based requests bypass AI agent processing and directly invoke MCP tools for faster, more predictable responses.\n\n" +
        "Validation Rules:\n" +
        "- summarise: Requires doc_id, validates level enum or word_count range\n" +
        "- translate: Requires doc_id and target_language\n" +
        "- search: Requires non-empty collection_id, validates limit range\n\n" +
        "Error Handling:\n" +
        "Intent processing failures include specific error context (tool not found, parameter validation, service errors) for debugging.\n\n" +
        "Collection Support:\n" +
        "Both modes support single collections (string) or multi-collection operations (array of collection IDs).\n\n" +
        "Use Cases:\n" +
        "- Traditional: 'What are the key findings in our Q4 report?'\n" +
        '- Intent-based: {"intent": "summarise", "level": "medium", "doc_id": "report_123"}\n\n' +
        "Session Management:\n" +
        "- session_id is optional; auto-generated using user_id and collection_id if not provided\n" +
        "- session_id is always returned in response for conversation continuity\n" +
        "- Required parameters vary by intent type",
    security: [
        {
            bearerAuth: [],
        },
    ],
    body: {
        type: "object",
        required: ["user_id"],
        properties: {
            query: {
                type: "string",
                description: "Natural language query for document analysis. Required for query-based mode, optional for intent-based mode.",
                minLength: 1,
                maxLength: 2000,
            },
            user_id: {
                type: "string",
                description: "User identifier for authentication and access control",
            },
            session_id: {
                type: "string",
                description: "Optional session identifier for conversation continuity. Auto-generated if not provided.",
            },
            collection_id: {
                anyOf: [
                    { type: "string" },
                    { type: "array", items: { type: "string" }, minItems: 1 },
                ],
                description: "Optional collection identifier(s). Required for search intent.",
            },
            doc_id: {
                type: "string",
                description: "Specific document identifier. Required for summarise and translate intents.",
            },
            intent: {
                type: "object",
                description: "Intent object for direct MCP tool invocation.",
                properties: {
                    intent: {
                        type: "string",
                        enum: ["summarise", "translate", "search"],
                        description: "The type of action to perform",
                    },
                    level: {
                        type: "string",
                        enum: ["concise", "medium", "detailed"],
                        description: "Detail level for summarization (summarise intent only)",
                    },
                    word_count: {
                        type: "number",
                        minimum: 10,
                        maximum: 2000,
                        description: "Target word count for summarization (summarise intent only)",
                    },
                    target_language: {
                        type: "string",
                        description: "Target language code for translation (translate intent only)",
                    },
                    limit: {
                        type: "number",
                        minimum: 1,
                        maximum: 20,
                        description: "Maximum search results (search intent only, default: 5)",
                    },
                },
                required: ["intent"],
                additionalProperties: false,
            },
        },
        anyOf: [{ required: ["query"] }, { required: ["intent"] }],
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
                collection_id: {
                    anyOf: [{ type: "string" }, { type: "array", items: { type: "string" } }],
                },
                timestamp: { type: "string" },
                query_type: {
                    type: "string",
                    enum: ["document_specific", "general", "intent_based"],
                },
                intent_type: { type: "string" },
                source_references: {
                    type: "array",
                    items: {
                        type: "object",
                        properties: {
                            document_name: { type: "string" },
                            page_number: { type: "number" },
                            chunk_id: { type: "number" },
                            source_reference: { type: "string" },
                            reference_type: { type: "string", enum: ["page", "chunk"] },
                            text_content: { type: "string" },
                        },
                        required: ["document_name", "source_reference", "reference_type"],
                    },
                },
                sources_count: { type: "number" },
            },
        },
    },
};
