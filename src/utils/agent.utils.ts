import {SourceReference} from "../types/ask.agent.types";
import {ExtractedContent} from "../types/ask.agent.types";

export class AgentUtils {
    static extractResponseContent(agentResponse: any): ExtractedContent {
        if (!agentResponse?.messages?.length) {
            throw new Error('Agent returned invalid response');
        }

        const lastMessage = agentResponse.messages[agentResponse.messages.length - 1];
        let ragResponse = null;

        if (agentResponse.messages.length >= 2) {
            const secondLastMessage = agentResponse.messages[agentResponse.messages.length - 2];
            if (secondLastMessage?.name?.includes('RAG') || secondLastMessage?.name?.includes('retrieve')) {
                ragResponse = secondLastMessage.content;
            }
        }

        if (!lastMessage?.content) {
            throw new Error('Agent response missing content');
        }

        const aiResponse = typeof lastMessage.content === 'string'
            ? lastMessage.content
            : JSON.stringify(lastMessage.content);

        return {
            aiResponse,
            ragResponse
        };
    }

    static validateRequest(query: string, userId: string, collectionId?: string | string[]): void {
        if (!query?.trim()) {
            throw new Error('Query is required and cannot be empty');
        }

        if (!userId) {
            throw new Error('user_id is required');
        }
    }

    static generateSessionId(userId: string, collectionId?: string | string[]): string {
        const timestamp = Date.now();
        const randomSuffix = Math.random().toString(36).substring(2, 8);

        if (collectionId && (Array.isArray(collectionId) ? collectionId.length > 0 : collectionId)) {
            const collectionIds: string[] = Array.isArray(collectionId) ? collectionId : [collectionId];
            const sessionCollectionId = collectionIds.join(',');
            return `${userId}_${sessionCollectionId}_${timestamp}_${randomSuffix}`;
        }

        return `${userId}_general_${timestamp}_${randomSuffix}`;
    }

    static extractSourceReferences(responseText: string, ragResponse: string | null = null): SourceReference[] {
        const sourceReferences: SourceReference[] = [];
        const seenRefs = new Set<string>();

        const citationPattern = /SOURCE_CITATION:\s*\\cite\{([^,]+),\s*(page|chunk)\s*([\d\-]+)\}/g;

        for (const match of responseText.matchAll(citationPattern)) {
            const documentName = match[1].trim();
            const refType = match[2] as 'page' | 'chunk';
            const refValue = match[3].trim();

            const numbers = this.parseNumberRange(refValue);

            for (const num of numbers) {
                const uniqueKey = `${documentName}_${refType}_${num}`;

                if (!seenRefs.has(uniqueKey)) {
                    seenRefs.add(uniqueKey);

                    const sourceRef: SourceReference = {
                        document_name: documentName,
                        source_reference: `${documentName}, ${refType === 'page' ? 'Page' : 'Chunk'} ${num}`,
                        reference_type: refType
                    };

                    if (refType === 'page') {
                        sourceRef.page_number = num;
                    } else {
                        sourceRef.chunk_id = num;
                    }

                    if (ragResponse) {
                        const textContent = this.extractTextForReference(ragResponse, documentName, refType, num);
                        if (textContent) {
                            sourceRef.text_content = textContent.text;
                        }
                    }

                    sourceReferences.push(sourceRef);
                }
            }
        }

        return sourceReferences;
    }

    private static extractTextForReference(
        ragResponse: string,
        documentName: string,
        refType: 'page' | 'chunk',
        refNumber: number
    ): { text: string } | null {
        const citationPattern = /SOURCE_CITATION:\s*\\cite\{([^,]+),\s*(page|chunk)\s*([\d\-]+)\}/g;
        const citations: Array<{
            match: RegExpMatchArray;
            index: number;
            documentName: string;
            refType: 'page' | 'chunk';
            refNumbers: number[];
        }> = [];

        let match;
        while ((match = citationPattern.exec(ragResponse)) !== null) {
            const docName = match[1].trim();
            const type = match[2] as 'page' | 'chunk';
            const refValue = match[3].trim();
            const numbers = this.parseNumberRange(refValue);

            citations.push({
                match,
                index: match.index,
                documentName: docName,
                refType: type,
                refNumbers: numbers
            });
        }

        const targetCitation = citations.find(citation =>
            citation.documentName === documentName &&
            citation.refType === refType &&
            citation.refNumbers.includes(refNumber)
        );

        if (!targetCitation) {
            return null;
        }

        let textStart = 0;
        let textEnd = targetCitation.index;

        const previousCitations = citations.filter(c => c.index < targetCitation.index);
        if (previousCitations.length > 0) {
            const prevCitation = previousCitations[previousCitations.length - 1];
            textStart = prevCitation.index + prevCitation.match[0].length;
        }

        let textContent = ragResponse.substring(textStart, textEnd).trim();

        textContent = textContent
            .replace(/\n\s*\n+/g, '\n\n')
            .replace(/[ \t]+/g, ' ')
            .trim();

        textContent = textContent
            .split('\n')
            .map(line => line.trim())
            .filter(line => line.length > 0)
            .join('\n');

        if (textContent) {
            return {text: textContent};
        }

        return null;
    }

    private static parseNumberRange(rangeStr: string): number[] {
        if (!rangeStr.includes('-')) {
            return [parseInt(rangeStr, 10)];
        }

        const [start, end] = rangeStr.split('-').map(s => parseInt(s.trim(), 10));
        const result: number[] = [];

        for (let i = start; i <= end; i++) {
            result.push(i);
        }

        return result;
    }
}