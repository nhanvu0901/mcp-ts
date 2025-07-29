import { MultiServerMCPClient } from '@langchain/mcp-adapters';
import { IntentRequest } from '../types/intent.types';

export class IntentUtils {

    static async processSummarizeIntent(
        mcpClient: MultiServerMCPClient,
        intent: IntentRequest,
        userId: string,
        docId?: string
    ): Promise<{ response: string; ragResponse: string | null }> {
        if (!docId) {
            throw new Error('Document ID is required for summarization');
        }

        try {
            // Get the tools from the DocDBSummarizationService
            const tools = await mcpClient.getTools('DocDBSummarizationService');
            let result: string;

            if (intent.word_count) {
                // Find the word count based summarization tool
                const wordCountTool = tools.find(tool => tool.name.includes('summarize_by_word_count'));
                if (!wordCountTool) {
                    throw new Error('Word count summarization tool not found');
                }

                result = await wordCountTool.invoke({
                    user_id: userId,
                    document_id: docId,
                    num_words: intent.word_count
                });
            } else {
                // Find the level based summarization tool
                const levelTool = tools.find(tool => tool.name.includes('summarize_by_detail_level'));
                if (!levelTool) {
                    throw new Error('Detail level summarization tool not found');
                }

                const level = intent.level || 'medium';
                result = await levelTool.invoke({
                    user_id: userId,
                    document_id: docId,
                    summarization_level: level
                });
            }

            return {
                response: result,
                ragResponse: null // Summarization doesn't produce RAG response
            };
        } catch (error) {
            throw new Error(`Summarization failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }


    static async processTranslateIntent(
        mcpClient: MultiServerMCPClient,
        intent: IntentRequest,
        userId: string,
        docId?: string
    ): Promise<{ response: string; ragResponse: string | null }> {
        if (!intent.target_language) {
            throw new Error('Target language is required for translation');
        }

        if (!docId) {
            throw new Error('Document ID is required for translation');
        }

        try {
            // Get the tools from the DocumentTranslationService
            const tools = await mcpClient.getTools('DocumentTranslationService');
            const translateTool = tools.find(tool => tool.name.includes('translate_document'));

            if (!translateTool) {
                throw new Error('Document translation tool not found');
            }

            const result = await translateTool.invoke({
                user_id: userId,
                document_id: docId,
                target_lang: intent.target_language
            });

            return {
                response: result,
                ragResponse: null // Translation doesn't produce RAG response
            };
        } catch (error) {
            throw new Error(`Translation failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    static async processSearchIntent(
        mcpClient: MultiServerMCPClient,
        intent: IntentRequest,
        userId: string,
        collectionId: string | string[],
        query: string = 'search documents' // Default query for intent-based search
    ): Promise<{ response: string; ragResponse: string | null }> {
        try {
            const collectionIds: string[] = Array.isArray(collectionId) ? collectionId : [collectionId];
            const limit = intent.limit || 5;

            // Get the tools from the RAGService
            const tools = await mcpClient.getTools('RAGService');
            const retrieveTool = tools.find(tool => tool.name.includes('retrieve'));

            if (!retrieveTool) {
                throw new Error('RAG retrieve tool not found');
            }

            const ragResponse = await retrieveTool.invoke({
                query: query,
                user_id: userId,
                collection_id: collectionIds,
                limit: limit
            });

            // For search intent, we return the RAG response directly
            const response = ragResponse ?
                `Found ${limit} relevant document:\n\n${ragResponse}` :
                'No relevant documents found.';

            return {
                response,
                ragResponse
            };
        } catch (error) {
            throw new Error(`Search failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    static async processIntent(
        mcpClient: MultiServerMCPClient,
        intent: IntentRequest,
        userId: string,
        collectionId: string | string[],
        docId?: string,
        fallbackQuery?: string
    ): Promise<{ response: string; ragResponse: string | null }> {
        switch (intent.intent) {
            case 'summarise':
                return await this.processSummarizeIntent(mcpClient, intent, userId, docId);

            case 'translate':
                return await this.processTranslateIntent(mcpClient, intent, userId, docId);

            case 'search':
                return await this.processSearchIntent(mcpClient, intent, userId, collectionId, fallbackQuery);

            default:
                throw new Error(`Unknown intent type: ${intent.intent}`);
        }
    }

    static validateIntent(intent: IntentRequest, docId?: string): void {
        if (!intent.intent) {
            throw new Error('Intent type is required');
        }

        switch (intent.intent) {
            case 'summarise':
                if (!docId) {
                    throw new Error('Document ID is required for summarization');
                }

                // Validate word_count if provided
                if (intent.word_count && intent.word_count < 10) {
                    throw new Error('Word count must be at least 10');
                }

                // Validate level if provided
                if (intent.level && !['concise', 'medium', 'detailed'].includes(intent.level)) {
                    throw new Error('Level must be one of: concise, medium, detailed');
                }

                // Ensure at least one summarization parameter is provided
                if (!intent.word_count && !intent.level) {
                    throw new Error('Either word_count or level must be provided for summarization');
                }

                break;

            case 'translate':
                if (!docId) {
                    throw new Error('Document ID is required for translation');
                }
                if (!intent.target_language) {
                    throw new Error('Target language is required for translation');
                }
                break;

            case 'search':
                if (intent.limit && intent.limit < 1) {
                    throw new Error('Search limit must be at least 1');
                }
                break;
        }
    }
}