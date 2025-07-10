export const DocumentUploadSchema = {
    tags: ["Documents"],
    summary: "Upload document with full processing and vectorization",
    description: "Upload a document file and process it with embeddings for vector search (embed=true)",
    consumes: ["multipart/form-data"],
    security: [
        {
            bearerAuth: []
        }
    ],
    response: {
        200: {
            description: "Document uploaded and processed successfully",
            type: "object",
            properties: {
                success: { type: "boolean" },
                doc_id: { type: "string" },
                doc_type: { type: "string" },
                session_id: { type: "string" },
                user_id: { type: "string" },
                filename: { type: "string" },
                collection_name: { type: "string" },
                embed: { type: "boolean" },
                processing_result: { type: "object" }
            }
        },
        400: {
            description: "Bad request - invalid file or missing parameters",
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

export const DocumentUploadMongoSchema = {
    tags: ["Documents"],
    summary: "Upload document to MongoDB only (no vectorization)",
    description: "Upload a document file and save to MongoDB without creating embeddings (embed=false)",
    consumes: ["multipart/form-data"],
    security: [
        {
            bearerAuth: []
        }
    ],
    body: {
        type: "object",
        required: ["file", "user_id"],
        properties: {
            file: {
                type: "string",
                format: "binary",
                description: "Document file to upload"
            },
            session_id: {
                type: "string",
                description: "Session identifier",
                default: "default"
            },
            user_id: {
                type: "string",
                description: "User identifier"
            }
        }
    },
    response: {
        200: {
            description: "Document uploaded to MongoDB successfully",
            type: "object",
            properties: {
                success: { type: "boolean" },
                doc_id: { type: "string" },
                doc_type: { type: "string" },
                session_id: { type: "string" },
                user_id: { type: "string" },
                filename: { type: "string" },
                embed: { type: "boolean" },
                mongo_saved: { type: "boolean" },
                processing_result: { type: "object" }
            }
        },
        400: {
            description: "Bad request - invalid file or missing parameters",
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