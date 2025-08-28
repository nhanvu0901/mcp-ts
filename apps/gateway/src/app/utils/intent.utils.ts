import { MultiServerMCPClient } from "@langchain/mcp-adapters";
import { IntentRequest } from "../types/intent.types";

export class IntentUtils {
    static async processSummarizeIntent(
        mcpClient: MultiServerMCPClient,
        intent: IntentRequest,
        userId: string,
        docId: string,
        query: string
    ): Promise<{ response: string; ragResponse: string | null }> {
        if (!docId) {
            throw new Error("Document ID is required for summarization");
        }

        try {
            const tools = await mcpClient.getTools("DocDBSummarizationService");
            let result: string;

            const summaryParams = {
                user_id: userId,
                document_id: docId,
                additional_instructions: query
            };

            if (intent.word_count) {
                const wordCountTool = tools.find((tool) =>
                    tool.name.includes("summarize_by_word_count")
                );
                if (!wordCountTool) {
                    throw new Error("Word count summarization tool not found");
                }

                result = await wordCountTool.invoke({
                    ...summaryParams,
                    num_words: intent.word_count
                });
            } else {
                const levelTool = tools.find((tool) =>
                    tool.name.includes("summarize_by_detail_level")
                );
                if (!levelTool) {
                    throw new Error("Detail level summarization tool not found");
                }

                const level = intent.level || "medium";
                result = await levelTool.invoke({
                    ...summaryParams,
                    summarization_level: level
                });
            }

            return {
                response: result,
                ragResponse: null,
            };
        } catch (error) {
            throw new Error(
                `Summarization failed: ${error instanceof Error ? error.message : String(error)}`
            );
        }
    }

    static async processTranslateIntent(
        mcpClient: MultiServerMCPClient,
        intent: IntentRequest,
        userId: string,
        docId: string,
        query: string
    ): Promise<{ response: string; ragResponse: string | null }> {
        if (!intent.target_language) {
            throw new Error("Target language is required for translation");
        }

        if (!docId) {
            throw new Error("Document ID is required for translation");
        }

        try {
            const tools = await mcpClient.getTools("DocumentTranslationService");
            const translateTool = tools.find((tool) => tool.name.includes("translate_document"));

            if (!translateTool) {
                throw new Error("Document translation tool not found");
            }

            const result = await translateTool.invoke({
                user_id: userId,
                document_id: docId,
                target_lang: intent.target_language,
                additional_instructions: query
            });

            return {
                response: result,
                ragResponse: null,
            };
        } catch (error) {
            throw new Error(
                `Translation failed: ${error instanceof Error ? error.message : String(error)}`
            );
        }
    }

    static async processSearchIntent(
        mcpClient: MultiServerMCPClient,
        intent: IntentRequest,
        userId: string,
        collectionId: string | string[],
        query: string
    ): Promise<{ response: string; ragResponse: string | null }> {
        if (!collectionId || (Array.isArray(collectionId) && collectionId.length === 0)) {
            throw new Error("Collection ID is required for search intent");
        }

        try {
            const collectionIds: string[] = Array.isArray(collectionId)
                ? collectionId
                : [collectionId];
            const limit = intent.limit || 5;

            const tools = await mcpClient.getTools("RAGService");
            const retrieveTool = tools.find((tool) => tool.name.includes("retrieve"));

            if (!retrieveTool) {
                throw new Error("RAG retrieve tool not found");
            }

            const ragResponse = await retrieveTool.invoke({
                query: query,
                user_id: userId,
                collection_id: collectionIds,
                limit: limit,
            });

            const response = ragResponse
                ? `Found ${limit} relevant documents:\n\n${ragResponse}`
                : "No relevant documents found.";

            return {
                response,
                ragResponse,
            };
        } catch (error) {
            throw new Error(
                `Search failed: ${error instanceof Error ? error.message : String(error)}`
            );
        }
    }

    static async processIntent(
        mcpClient: MultiServerMCPClient,
        intent: IntentRequest,
        userId: string,
        query: string,
        collectionId?: string | string[],
        docId?: string
    ): Promise<{ response: string; ragResponse: string | null }> {
        switch (intent.intent) {
            case "summarise":
                return await this.processSummarizeIntent(mcpClient, intent, userId, docId!, query);

            case "translate":
                return await this.processTranslateIntent(mcpClient, intent, userId, docId!, query);

            case "search":
                return await this.processSearchIntent(
                    mcpClient,
                    intent,
                    userId,
                    collectionId!,
                    query
                );

            default:
                throw new Error(`Unknown intent type: ${intent.intent}`);
        }
    }

    static validateIntent(
        intent: IntentRequest,
        docId?: string,
        collectionId?: string | string[]
    ): void {
        if (!intent.intent) {
            throw new Error("Intent type is required");
        }

        switch (intent.intent) {
            case "summarise":
                if (!docId) {
                    throw new Error("Document ID is required for summarization intent");
                }
                if (intent.level && !["concise", "medium", "detailed"].includes(intent.level)) {
                    throw new Error("Level must be one of: concise, medium, detailed");
                }
                break;

            case "translate":
                if (!docId) {
                    throw new Error("Document ID is required for translation intent");
                }
                if (!intent.target_language) {
                    throw new Error("Target language is required for translation intent");
                }
                break;

            case "search":
                if (!collectionId || (Array.isArray(collectionId) && collectionId.length === 0)) {
                    throw new Error("Collection ID is required for search intent");
                }
                if (intent.limit && intent.limit < 1) {
                    throw new Error("Search limit must be at least 1");
                }
                break;

            default:
                throw new Error(`Invalid intent type: ${intent.intent}`);
        }
    }
}
