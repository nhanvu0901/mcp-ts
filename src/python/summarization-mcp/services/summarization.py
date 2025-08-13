import asyncio
import json
from enum import Enum
from typing import Literal, Optional, Tuple

import regex as re
import semchunk
import tiktoken
from lingua import Language, LanguageDetectorBuilder
from motor.motor_asyncio import AsyncIOMotorClient
from langchain_core.messages import HumanMessage, SystemMessage
from .utils import get_llm_client

detector = LanguageDetectorBuilder.from_all_languages().with_preloaded_language_models().build()
encoding = tiktoken.encoding_for_model("gpt-4o-mini")

class SummarizationLevel(Enum):
    CONCISE = "concise"
    MEDIUM = "medium"
    DETAILED = "detailed"

SupportedLanguage = Literal["English", "Czech", "Slovakia"]

CHUNK_PROMPT = """As a professional summarizer, generate a structured JSON output for the provided text chunk. Your output must follow these guidelines:

1. Title: Create a short, clear, and compelling title (within 5-10 words) that captures the core idea or theme of the text chunk.
2. Summary: Create a coherent list of {bullet_num} bullet points that accurately capture the essential points of the text chunk. Each bullet point should be 15-20 words and a complete, meaningful sentence.
3. Content Integrity: Ensure the summary strictly reflects the content of the chunk without introducing external information.
4. JSON Structure: Return the result as a JSON object with two fields: `title` and `summary`.

CRITICAL: Your response must be ONLY a valid JSON object. Do not include any markdown formatting, code blocks, or additional text. Start your response with {{ and end with }}.

The text chunk:
{chunk}

JSON Response:"""

REFINE_PROMPT = """Divide the following summary into well-structured paragraphs and return the output under the JSON key `summary`.

The summary:
{merged_summaries}

Further instruction: {further_instruction}

CRITICAL: Your response must be ONLY a valid JSON object with the key `summary`. Do not include any markdown formatting, code blocks, or additional text. Start your response with {{ and end with }}.

JSON Response:"""

CHUNK_SYS_PROMPT = """You are a helpful AI that excels at summarization. You must respond with ONLY a valid JSON object containing exactly two keys: `title` and `summary`. 

CRITICAL RULES:
- Do not use markdown code blocks (no ```json or ```)
- Do not include any explanatory text before or after the JSON
- Start your response with { and end with }
- Unless otherwise instructed, always return the output in the original language of the document"""

SYS_PROMPT = """You are a helpful AI that excels at summarization. You must respond with ONLY a valid JSON object containing exactly one key: `summary`.

CRITICAL RULES:
- Do not use markdown code blocks (no ```json or ```)
- Do not include any explanatory text before or after the JSON
- Start your response with { and end with }
- Unless otherwise instructed, always return the output in the original language of the document"""

SYS_PROMPT_ADD = " Always return the output in {lang}."

async def process_markdown_string(md_string: str) -> str:
    md_string = re.sub(r"\*\*(.*?)\*\*|\*(.*?)\*", r"\1\2", md_string)
    md_string = re.sub(r"\n\n-----\n\n", "\n", md_string)
    return re.sub(r"(?<!\.)\n\n(?=[\p{Ll}\p{M}])", "\n", md_string)

def detect_language(text: str) -> SupportedLanguage:
    try:
        language = detector.detect_language_of(text)
        if language is None or language not in (Language.ENGLISH, Language.CZECH, Language.SLOVAK):
            return "English"
        
        if language == Language.ENGLISH:
            return "English"
        elif language == Language.CZECH:
            return "Czech"
        elif language == Language.SLOVAK:
            return "Slovakia"
        else:
            return "English"
    except Exception:
        return "English"

def get_chunker(max_token_chars: int = 1024):
    return semchunk.chunkerify("gpt-4o", max_token_chars)

def chunk_text(text: str, max_token_chars: int = 1024):
    chunker = get_chunker(max_token_chars)
    return chunker(text)

def token_count(text: str) -> int:
    return len(encoding.encode(text))

def word_count(text: str) -> int:
    return len(text.split())

class DocumentSummarizer:
    def __init__(self, mongo_client: AsyncIOMotorClient):
        self.llm_client = get_llm_client()
        self.mongo_client = mongo_client
        self.db = mongo_client.ai_assistant
        self.collection = self.db.documents
        
        self.bullet_mapping = {
            512: {
                SummarizationLevel.CONCISE: 3,
                SummarizationLevel.MEDIUM: 4,
                SummarizationLevel.DETAILED: 5,
            },
            1024: {
                SummarizationLevel.CONCISE: 4,
                SummarizationLevel.MEDIUM: 6,
                SummarizationLevel.DETAILED: 8,
            },
            2048: {
                SummarizationLevel.CONCISE: 4,
                SummarizationLevel.MEDIUM: 8,
                SummarizationLevel.DETAILED: 12,
            },
        }

    async def _get_document(self, user_id: str, document_id: str) -> Optional[dict]:
        return await self.collection.find_one({
            "_id": document_id,
            "user_id": user_id,
            "type": {"$ne": "collection"}
        })

    async def _llm_complete(self, messages, **kwargs):
        langchain_messages = []
        for msg in messages:
            if msg["role"] == "system":
                langchain_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))

        response = await self.llm_client.ainvoke(langchain_messages)
        return json.loads(response.content)

    async def _summarize_chunk(self, chunk: str, bullet_num: int, lang: Optional[SupportedLanguage]) -> Tuple[str, list]:
        system_prompt = CHUNK_SYS_PROMPT
        if lang:
            system_prompt += SYS_PROMPT_ADD.format(lang=lang)
        
        user_message = CHUNK_PROMPT.format(chunk=chunk, bullet_num=bullet_num)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        
        content = await self._llm_complete(messages, response_format={"type": "json_object"})
        return content["title"], content["summary"]

    async def _summarize_multiple_chunks(self, text: str, level: SummarizationLevel, lang: Optional[SupportedLanguage]) -> str:
        text_length = token_count(text)
        
        if text_length < 2048:
            max_token_per_chunk = 512
        elif text_length < 4096:
            max_token_per_chunk = 1024
        else:
            max_token_per_chunk = 2048
            
        bullet_num = self.bullet_mapping[max_token_per_chunk][level]
        chunks = chunk_text(text, max_token_per_chunk)
        
        tasks = [self._summarize_chunk(chunk, bullet_num, lang) for chunk in chunks]
        results = await asyncio.gather(*tasks)
        
        chunk_summaries = []
        for _, chunk_summary in results:
            bullet_points = "\n".join(chunk_summary)
            chunk_summaries.append(f"{bullet_points}\n")
        
        return "".join(chunk_summaries)

    async def _refine_summaries(self, merged_summaries: str, lang: Optional[SupportedLanguage], further_instruction: str) -> str:
        system_prompt = SYS_PROMPT
        if lang:
            system_prompt += SYS_PROMPT_ADD.format(lang=lang)
        
        user_message = REFINE_PROMPT.format(
            merged_summaries=merged_summaries,
            further_instruction=further_instruction
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        
        content = await self._llm_complete(messages, response_format={"type": "json_object"})
        return content["summary"]

    async def summarize_document(
        self,
        user_id: str,
        document_id: str,
        level: str = "medium",
        further_instruction: Optional[str] = None
    ) -> Tuple[str, int]:
        document = await self._get_document(user_id, document_id)
        if not document:
            raise ValueError(f"Document not found for user {user_id} and document {document_id}")
        
        text = document.get("text", "")
        if not text:
            raise ValueError("Document has no text content")
        
        text = await process_markdown_string(text)
        
        try:
            summ_level = SummarizationLevel[level.upper()]
        except KeyError:
            summ_level = SummarizationLevel.MEDIUM
        
        text_sample = text[:min(len(text), 1000)]
        lang = detect_language(text_sample)
        
        if not further_instruction:
            further_instruction = ""
        
        merged_summary = await self._summarize_multiple_chunks(text, summ_level, lang)
        chunks = chunk_text(merged_summary, 400)
        merged_summary = "\n\n".join(chunks)
        
        final_summary = await self._refine_summaries(merged_summary, lang, further_instruction)
        
        return final_summary, word_count(final_summary)

    async def summarize_document_with_word_count(
        self,
        user_id: str,
        document_id: str,
        num_words: int = 100
    ) -> Tuple[str, int]:
        if num_words <= 50:
            level = "concise"
        elif num_words <= 150:
            level = "medium"
        else:
            level = "detailed"
        
        instruction = f"Create a summary with approximately {num_words} words."
        
        return await self.summarize_document(user_id, document_id, level, instruction)