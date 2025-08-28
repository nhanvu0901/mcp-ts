import asyncio
import json
from typing import Optional, Tuple
import semchunk
from motor.motor_asyncio import AsyncIOMotorClient
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
import os
LLM_TRANSLATION_MODEL: str = os.getenv("LLM_TRANSLATION_MODEL")

def get_chunker(max_token_chars: int = 1024):
    return semchunk.chunkerify(LLM_TRANSLATION_MODEL, max_token_chars)


def chunk_text(text: str, max_token_chars: int = 1024):
    chunker = get_chunker(max_token_chars)
    return chunker(text)


class DocumentTranslator:
    def __init__(self, mongo_client: AsyncIOMotorClient, llm_client: ChatOpenAI):
        self.mongo_client = mongo_client
        self.llm_client = llm_client
        self.db = mongo_client.ai_assistant
        self.collection = self.db.documents

        self.translate_prompt = """You must translate the following text to {target_lang} and return ONLY a valid JSON object. Do not include any other text, explanations, or formatting.

The JSON must have exactly this structure:
{{"translated_text": "your translated text here"}}

Requirements:
- Return ONLY the JSON object
- No markdown formatting or code blocks
- The translated_text value must be a single string
- Preserve the original meaning and tone
- Do not add any additional keys or fields

Additional instructions: {additional_instructions}

Text to translate: {chunk}

JSON response:"""

        self.sys_prompt = "You are a professional translator. You must respond with valid JSON only. Never include explanations, markdown formatting, or any text outside the JSON object."

    async def _get_document(self, user_id: str, document_id: str) -> Optional[dict]:
        try:
            return await self.collection.find_one({
                "_id": document_id,
                "user_id": user_id,
                "type": {"$ne": "collection"}
            })
        except Exception as e:
            print(f"Database error: {e}")
            return None

    async def _translate_chunk(self, chunk: str, target_lang: str, additional_instructions: str = "") -> str:
        user_message = self.translate_prompt.format(
            chunk=chunk,
            target_lang=target_lang,
            additional_instructions=additional_instructions
        )

        messages = [
            SystemMessage(content=self.sys_prompt),
            HumanMessage(content=user_message)
        ]

        try:
            response = await self.llm_client.ainvoke(messages)
            response_content = json.loads(response.content)
            translated_text = response_content.get("translated_text", "")

            if isinstance(translated_text, list):
                translated_text = " ".join(map(str, translated_text))
            elif not isinstance(translated_text, str):
                translated_text = str(translated_text)

            return translated_text
        except Exception as e:
            print(f"Translation failed for chunk: {e}")
            return chunk

    async def translate_text(self, text: str, target_lang: str, additional_instructions: str = "") -> str:
        try:
            chunks = chunk_text(text, 1024)
            tasks = [self._translate_chunk(chunk, target_lang, additional_instructions) for chunk in chunks]
            translated_chunks = await asyncio.gather(*tasks)
            return " ".join(translated_chunks)
        except Exception as e:
            print(f"Text translation failed: {e}")
            return text

    async def translate_document(
        self,
        user_id: str,
        document_id: str,
        target_lang: str,
        additional_instructions: Optional[str] = None
    ) -> Tuple[str, int]:
        document = await self._get_document(user_id, document_id)
        if not document:
            raise ValueError(f"Document not found for user {user_id} and document {document_id}")

        text = document.get("text", "")
        if not text:
            raise ValueError("Document has no text content")

        instructions = additional_instructions or ""
        translated_text = await self.translate_text(text, target_lang, instructions)
        word_count = len(translated_text.split())

        return translated_text, word_count
