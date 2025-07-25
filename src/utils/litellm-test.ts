import axios from 'axios';

interface LiteLLMTestResult {
    proxyRunning: boolean;
    authWorking: boolean;
    modelsAvailable: boolean;
    error?: string;
}

export class LiteLLMTester {
    private proxyUrl: string;
    private masterKey: string;

    constructor(proxyUrl: string, masterKey: string) {
        this.proxyUrl = proxyUrl;
        this.masterKey = masterKey;
    }

    async testConnection(): Promise<LiteLLMTestResult> {
        const result: LiteLLMTestResult = {
            proxyRunning: false,
            authWorking: false,
            modelsAvailable: false
        };

        try {
            // Test 1: Check if proxy is running
            console.log('Testing LiteLLM proxy connection...');
            await axios.get(`${this.proxyUrl}/health`, { timeout: 5000 });
            result.proxyRunning = true;
            console.log('✅ LiteLLM proxy is running');

            // Test 2: Test authentication
            console.log('Testing authentication...');
            const modelsResponse = await axios.get(`${this.proxyUrl}/v1/models`, {
                headers: {
                    'Authorization': `Bearer ${this.masterKey}`,
                    'Content-Type': 'application/json'
                },
                timeout: 10000
            });
            
            result.authWorking = true;
            result.modelsAvailable = modelsResponse.data.data?.length > 0;
            console.log('✅ Authentication successful');
            console.log(`✅ Found ${modelsResponse.data.data?.length || 0} models`);

            return result;

        } catch (error: any) {
            console.error('❌ LiteLLM connection test failed:', error.message);
            
            if (error.code === 'ECONNREFUSED') {
                result.error = 'LiteLLM proxy is not running or not accessible';
            } else if (error.response?.status === 401) {
                result.error = 'Authentication failed - invalid API key';
            } else if (error.response?.status === 403) {
                result.error = 'Access forbidden - check API key permissions';
            } else {
                result.error = error.response?.data?.error || error.message;
            }

            return result;
        }
    }

    async generateTestKey(): Promise<string | null> {
        try {
            console.log('Attempting to generate a new API key...');
            const response = await axios.post(`${this.proxyUrl}/key/generate`, {
                duration: '30d',
                models: ['ace-gpt-4o'],
                aliases: {},
                config: {},
                spend: 0,
                user_id: 'test-user',
                team_id: 'test-team'
            }, {
                headers: {
                    'Authorization': `Bearer ${this.masterKey}`,
                    'Content-Type': 'application/json'
                },
                timeout: 10000
            });

            const newKey = response.data.key;
            console.log('✅ Generated new API key:', newKey);
            return newKey;

        } catch (error: any) {
            console.error('❌ Failed to generate API key:', error.response?.data || error.message);
            return null;
        }
    }
}

export async function testLiteLLMSetup(proxyUrl: string, masterKey: string): Promise<void> {
    const tester = new LiteLLMTester(proxyUrl, masterKey);
    const result = await tester.testConnection();

    console.log('\n=== LiteLLM Test Results ===');
    console.log('Proxy Running:', result.proxyRunning ? '✅' : '❌');
    console.log('Authentication:', result.authWorking ? '✅' : '❌');
    console.log('Models Available:', result.modelsAvailable ? '✅' : '❌');
    
    if (result.error) {
        console.log('Error:', result.error);
        
        // Suggest fixes based on the error
        if (result.error.includes('not running')) {
            console.log('\n💡 Suggested fixes:');
            console.log('1. Start LiteLLM proxy: docker-compose up -d litellm');
            console.log('2. Check if port 4000 is available');
            console.log('3. Verify Docker containers are running');
        } else if (result.error.includes('Authentication failed')) {
            console.log('\n💡 Suggested fixes:');
            console.log('1. Check LITELLM_MASTER_KEY in .env file');
            console.log('2. Restart LiteLLM proxy after changing the key');
            console.log('3. Try generating a new API key');
            
            // Try to generate a new key
            if (result.proxyRunning) {
                const newKey = await tester.generateTestKey();
                if (newKey) {
                    console.log('4. Use this new key:', newKey);
                }
            }
        }
    }
}