db = db.getSiblingDB('ai_assistant');

db.createUser({
    user: 'ai_user',
    pwd: 'ai_password123',
    roles: [
        {role: 'readWrite', db: 'ai_assistant'},
        {role: 'dbAdmin', db: 'ai_assistant'}
    ]
});

// Create collections
db.createCollection('collections');
db.createCollection('documents');
db.createCollection('chat_memory');
db.createCollection('chat_summaries');

// Create indexes for better performance
db.chat_summaries.createIndex({ sessionId: 1, summaryIndex: 1 }, { unique: true });
db.chat_summaries.createIndex({ sessionId: 1, createdAt: -1 });
db.chat_summaries.createIndex({ createdAt: 1 }, { expireAfterSeconds: 2592000 }); // 30 days TTL

db.chat_memory.createIndex({ SessionId: 1 });
db.chat_memory.createIndex({ CreatedAt: -1 });

print('Database, collections, and indexes created successfully');