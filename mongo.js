db = db.getSiblingDB("ai_assistant");

db.createUser({
    user: "ai_user",
    pwd: "ai_password123",
    roles: [
        { role: "readWrite", db: "ai_assistant" },
        { role: "dbAdmin", db: "ai_assistant" },
    ],
});

// Create collections
db.createCollection("collections");
db.createCollection("documents");
db.createCollection("chat_memory");
db.createCollection("chat_summaries");

// Create indexes for chat_memory collection
db.chat_memory.createIndex({ SessionId: 1 }, { unique: true });
db.chat_memory.createIndex({ user_id: 1, UpdatedAt: -1 });
db.chat_memory.createIndex({ collection_id: 1 });
db.chat_memory.createIndex({ user_id: 1, collection_id: 1 });
db.chat_memory.createIndex({ UpdatedAt: -1 });
db.chat_memory.createIndex({ CreatedAt: -1 });

// Create indexes for documents collection
db.documents.createIndex({ user_id: 1, upload_date: -1 });
db.documents.createIndex({ user_id: 1, normalized_name: 1 });
db.documents.createIndex({ user_id: 1, collection_id: 1 });
