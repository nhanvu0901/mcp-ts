import asyncio
import json
import logging
import time
from typing import List, Any, Tuple, Dict, Optional
from langchain_openai import AzureChatOpenAI
from .config import config

logger = logging.getLogger(__name__)


class LLMRerankerService:
    """
    LLM-powered reranking service using GPT-4o mini for relevance scoring.

    Evaluates search candidates against user queries to improve result ranking
    through semantic understanding beyond traditional similarity metrics.
    """

    def __init__(self, llm_client: AzureChatOpenAI):
        self.llm_client = llm_client
        self.batch_size = config.RERANKER_BATCH_SIZE
        self.max_tokens = config.RERANKER_MAX_TOKENS
        self.temperature = config.RERANKER_TEMPERATURE
        self.timeout = config.RERANKER_TIMEOUT

    async def rerank_results(self, query: str, candidates: List[Any], limit: int) -> List[Any]:
        """
        Rerank search results using LLM-based relevance scoring.

        Args:
            query: User search query
            candidates: List of search results to rerank
            limit: Maximum number of results to return

        Returns:
            Reranked results with enhanced metadata
        """
        if not candidates:
            return []

        try:
            start_time = time.time()
            logger.info(f"Starting LLM reranking for {len(candidates)} candidates")

            scored_candidates = await self._batch_process_candidates(query, candidates)

            reranked_results = sorted(scored_candidates, key=lambda x: x[1], reverse=True)[:limit]

            enhanced_results = []
            for rank, (result, reranker_score) in enumerate(reranked_results, 1):
                result.payload['reranker_score'] = reranker_score
                result.payload['final_rank'] = rank
                enhanced_results.append(result)

            processing_time = (time.time() - start_time) * 1000
            logger.info(f"Reranking completed in {processing_time:.2f}ms, returned {len(enhanced_results)} results")

            return enhanced_results

        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            return self._create_fallback_results(candidates[:limit])

    async def _batch_process_candidates(self, query: str, candidates: List[Any]) -> List[Tuple[Any, int]]:
        """
        Process candidates in batches for efficient LLM evaluation.

        Args:
            query: User search query
            candidates: List of search result candidates

        Returns:
        Returns:
            List of (result, score) tuples
        """
        scored_results = []

        # Process candidates in batches to avoid rate limits
        for i in range(0, len(candidates), self.batch_size):
            batch = candidates[i:i + self.batch_size]
            batch_tasks = [self._score_candidate(query, candidate) for candidate in batch]

            try:
                batch_scores = await asyncio.wait_for(
                    asyncio.gather(*batch_tasks, return_exceptions=True),
                    timeout=self.timeout
                )

                for candidate, score_result in zip(batch, batch_scores):
                    if isinstance(score_result, Exception):
                        logger.warning(f"Failed to score candidate: {score_result}")
                        scored_results.append((candidate, 50))
                    else:
                        scored_results.append((candidate, score_result))

            except asyncio.TimeoutError:
                logger.warning(f"Batch processing timeout for batch {i // self.batch_size + 1}")
                # Add fallback scores for timed out batch
                for candidate in batch:
                    scored_results.append((candidate, 50))

        return scored_results

    async def _score_candidate(self, query: str, candidate: Any) -> int:
        """
        Score individual candidate using LLM relevance evaluation.

        Args:
            query: User search query
            candidate: Single search result candidate

        Returns:
            Relevance score (0-100)
        """
        try:
            text = candidate.payload.get('text', '')
            metadata = {
                'document_name': candidate.payload.get('document_name', 'Unknown'),
                'page_number': candidate.payload.get('page_number'),
                'file_type': candidate.payload.get('file_type', ''),
                'original_score': getattr(candidate, 'score', 0)
            }

            prompt = self._construct_relevance_prompt(query, text, metadata)

            response = await self.llm_client.ainvoke(
                [{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            score = self._parse_llm_response(response.content)
            return score

        except Exception as e:
            logger.warning(f"Error scoring candidate: {e}")
            return 50

    def _construct_relevance_prompt(self, query: str, passage: str, metadata: Dict) -> str:
        """
        Construct structured prompt for relevance evaluation.

        Args:
            query: User search query
            passage: Document passage text
            metadata: Document metadata

        Returns:
            Formatted prompt string
        """
        return f"""Score how well this passage answers the search query. Return only a number 0-100.

QUERY: "{query}"

PASSAGE: {passage}

SCORING:
90-100: Perfect match, directly answers query
80-89: Highly relevant, addresses main points  
70-79: Relevant but incomplete
60-69: Somewhat relevant
40-59: Marginally relevant
20-39: Poorly relevant
0-19: Not relevant

Score:"""

    def _parse_llm_response(self, response: str) -> int:
        """
        Parse LLM response to extract score only.

        Args:
            response: Raw LLM response text

        Returns:
            Relevance score (0-100)
        """
        try:
            # Clean response text and extract number
            response = response.strip()

            # Try to find a number in the response
            import re
            numbers = re.findall(r'\d+', response)

            if numbers:
                score = int(numbers[0])
                # Validate score range
                score = max(0, min(100, score))
                return score
            else:
                logger.warning(f"No number found in LLM response: {response[:50]}")
                return 50

        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse LLM response: {e}, response: {response[:50]}")
            return 50

    def _create_fallback_results(self, candidates: List[Any]) -> List[Any]:
        """
        Create fallback results when reranking fails.

        Args:
            candidates: Original search candidates

        Returns:
            Candidates with default reranker attributes
        """
        fallback_results = []
        for rank, candidate in enumerate(candidates, 1):
            candidate.reranker_score = 50  # Neutral fallback score
            candidate.final_rank = rank
            fallback_results.append(candidate)

        return fallback_results


def create_reranking_metadata(enabled: bool,
                              candidates_processed: int,
                              final_results: int,
                              processing_time_ms: float) -> Dict[str, Any]:
    """
    Create reranking metadata for response.

    Args:
        enabled: Whether reranking was enabled
        candidates_processed: Number of candidates processed
        final_results: Number of final results returned
        processing_time_ms: Processing time in milliseconds

    Returns:
        Metadata dictionary
    """
    return {
        "enabled": enabled,
        "model_used": config.RERANKER_MODEL_NAME if enabled else None,
        "candidates_processed": candidates_processed,
        "final_results": final_results,
        "processing_time_ms": round(processing_time_ms, 2) if enabled else 0
    }