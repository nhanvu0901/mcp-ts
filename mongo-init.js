
db = db.getSiblingDB('ai_assistant');

db.createUser({
  user: 'ai_user',
  pwd: 'ai_password123',
  roles: [
    { role: 'readWrite', db: 'ai_assistant' },
    { role: 'dbAdmin', db: 'ai_assistant' }
  ]
});

db.createCollection('collections');
db.createCollection('documents');

print('Database and user created successfully');