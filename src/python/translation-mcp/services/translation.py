import asyncio
import json
from typing import Optional, Tuple
import semchunk
from motor.motor_asyncio import AsyncIOMotorClient
from langchain_openai import AzureChatOpenAI

def get_chunker(max_token_chars: int = 1024):
    return semchunk.chunkerify("gpt-4o", max_token_chars)

def chunk_text(text: str, max_token_chars: int = 1024):
    chunker = get_chunker(max_token_chars)
    return chunker(text)

class DocumentTranslator:
    def __init__(self, mongo_client: AsyncIOMotorClient, llm_client: AzureChatOpenAI):
        self.mongo_client = mongo_client
        self.llm_client = llm_client
        self.db = mongo_client.ai_assistant
        self.collection = self.db.documents
        
        self.translate_prompt = """Translate the following text to {target_lang} and provide the result as a JSON object with a single key 'translated_text'. The value must be a single string, not a list or array.

Example:
{{
  "translated_text": "This is the translated sentence."
}}

Text: {chunk}"""
        
        self.sys_prompt = "You are a professional translator. Your task is to accurately translate the given text into the specified language, maintaining the original meaning and tone."

    async def _get_document(self, user_id: str, document_id: str) -> Optional[dict]:
        return await self.collection.find_one({
            "_id": document_id,
            "user_id": user_id,
            "type": {"$ne": "collection"}
        })

    async def _translate_chunk(self, chunk: str, target_lang: str) -> str:
        user_message = self.translate_prompt.format(chunk=chunk, target_lang=target_lang)
        
        messages = [
            {"role": "system", "content": self.sys_prompt},
            {"role": "user", "content": user_message},
        ]
        
        response = await self.llm_client.ainvoke(messages)
        content = json.loads(response.content)
        
        translated_text = content.get("translated_text", "")
        
        if isinstance(translated_text, list):
            translated_text = " ".join(map(str, translated_text))
        elif not isinstance(translated_text, str):
            translated_text = str(translated_text)
        
        return translated_text

    async def translate_text(self, text: str, target_lang: str) -> str:
        chunks = chunk_text(text, 1024)
        tasks = [self._translate_chunk(chunk, target_lang) for chunk in chunks]
        translated_chunks = await asyncio.gather(*tasks)
        return " ".join(translated_chunks)

    async def translate_document(self, user_id: str, document_id: str, target_lang: str) -> Tuple[str, int]:
        document = await self._get_document(user_id, document_id)
        if not document:
            raise ValueError(f"Document not found for user {user_id} and document {document_id}")
        
        text = document.get("text", "")
        if not text:
            raise ValueError("Document has no text content")
        
        translated_text = await self.translate_text(text, target_lang)
        word_count = len(translated_text.split())
        
        return translated_text, word_count