import { ChatOpenAI } from '@langchain/openai';

export function setupLiteLLMModel(
    modelName: string,
    apiKey: string,
    proxyUrl: string,
    temperature = 0.1,
    maxTokens = 5000
): ChatOpenAI {
    if (!proxyUrl.startsWith('http')) {
        throw new Error(`Invalid LiteLLM proxy URL format: ${proxyUrl}`);
    }

    try {
        new URL(proxyUrl);
    } catch (error) {
        throw new Error(`Invalid LiteLLM proxy URL: ${proxyUrl}`);
    }

    return new ChatOpenAI({
        model: modelName,
        apiKey: apiKey,
        configuration: {
            baseURL: proxyUrl + '/v1',
        },
        temperature,
        maxTokens,
    });
}
