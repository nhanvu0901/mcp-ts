export interface SourceReference {
    document_name: string;
    page_number?: number;
    chunk_id?: number;
    source_reference: string;
    reference_type: 'page' | 'chunk';
}

export class AgentUtils {
    static extractResponseContent(agentResponse: any): string {
        if (!agentResponse?.messages?.length) {
            throw new Error('Agent returned invalid response');
        }

        const lastMessage = agentResponse.messages[agentResponse.messages.length - 1];

        if (!lastMessage?.content) {
            throw new Error('Agent response missing content');
        }

        return typeof lastMessage.content === 'string'
            ? lastMessage.content
            : JSON.stringify(lastMessage.content);
    }

    static validateRequest(query: string, userId: string, collectionId: string): void {
        if (!query?.trim()) {
            throw new Error('Query is required and cannot be empty');
        }

        if (!userId) {
            throw new Error('user_id is required');
        }

        if (!collectionId) {
            throw new Error('collection_id is required');
        }
    }

    static extractSourceReferences(responseText: string): SourceReference[] {
        const sourceReferences: SourceReference[] = [];
        const seenRefs = new Set<string>();

        // Regex handles both single numbers and ranges: page 1, page 1-2, chunk 3, etc.
        const citationPattern = /SOURCE_CITATION:\s*\\cite\{([^,]+),\s*(page|chunk)\s*([\d\-]+)\}/g;

        for (const match of responseText.matchAll(citationPattern)) {
            const documentName = match[1].trim();
            const refType = match[2] as 'page' | 'chunk';
            const refValue = match[3].trim(); // Could be "1" or "1-2"

            // Parse range or single number
            const numbers = this.parseNumberRange(refValue);

            // Create separate objects for each number in the range
            for (const num of numbers) {
                const uniqueKey = `${documentName}_${refType}_${num}`;

                if (!seenRefs.has(uniqueKey)) {
                    seenRefs.add(uniqueKey);

                    const sourceRef: SourceReference = {
                        document_name: documentName,
                        source_reference: `${documentName}, ${refType === 'page' ? 'Page' : 'Chunk'} ${num}`,
                        reference_type: refType
                    };

                    // Add page_number or chunk_id
                    if (refType === 'page') {
                        sourceRef.page_number = num;
                    } else {
                        sourceRef.chunk_id = num;
                    }

                    sourceReferences.push(sourceRef);
                }
            }
        }

        return sourceReferences;
    }

    private static parseNumberRange(rangeStr: string): number[] {
        // Handle single number: "1" -> [1]
        if (!rangeStr.includes('-')) {
            return [parseInt(rangeStr, 10)];
        }

        // Handle range: "1-2" -> [1, 2], "5-10" -> [5, 6, 7, 8, 9, 10]
        const [start, end] = rangeStr.split('-').map(s => parseInt(s.trim(), 10));
        const result: number[] = [];

        for (let i = start; i <= end; i++) {
            result.push(i);
        }

        return result;
    }
}