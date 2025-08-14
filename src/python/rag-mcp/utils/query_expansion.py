import hashlib
import time
import logging
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from langchain_openai import AzureChatOpenAI
from .hybrid_search import HybridSearchService
from .fusion_score import FusionService
from .config import config
from langchain_core.messages import HumanMessage, SystemMessage
logger = logging.getLogger(__name__)


MAX_QUERY_VARIANTS = config.MAX_QUERY_VARIANTS

expansion_metrics = {
    "queries_expanded": 0,
    "variants_generated": 0,
    "deduplication_savings": 0,
    "average_expansion_time": 0.0,
    "fusion_method_usage": defaultdict(int),
    "total_expansion_time": 0.0,
    "successful_expansions": 0,
    "failed_expansions": 0
}
EXPANSION_FUSION_METHOD = config.EXPANSION_FUSION_METHOD

class QueryExpansionService:
    """
    Handles generation of query variants for improved retrieval coverage.

    This service uses LLM-based paraphrasing to generate alternative formulations
    of user queries, helping bridge vocabulary gaps between user language and
    document terminology.
    """

    def __init__(self, llm_client: AzureChatOpenAI,hybrid_search_service: HybridSearchService,fusion_service: FusionService):
        self.llm_client = llm_client
        self.hybrid_search_service = hybrid_search_service
        self.fusion_service = fusion_service

    def format_results_response(self,results: List[Any]) -> str:
        """
        Format search results with inline citations.

        Args:
            results: List of search results from Qdrant

        Returns:
            Formatted text with SOURCE_CITATION markers
        """
        if not results:
            return "No relevant documents found."

        formatted_results = []
        for i, result in enumerate(results):
            text = result.payload.get('text', str(result.payload))
            document_name = result.payload.get('document_name', 'Unknown Document')
            page_number = result.payload.get('page_number', 1)
            chunk_id = result.payload.get('chunk_id', i)
            file_type = result.payload.get('file_type', '').lower()
            score = getattr(result, 'score', 0.0)

            # Generate appropriate citation format
            if file_type in ['pdf', 'doc', 'docx', 'pptx', 'ppt']:
                citation = f"SOURCE_CITATION: \\cite{{{document_name}, page {page_number}}}"
            else:
                citation = f"SOURCE_CITATION: \\cite{{{document_name}, chunk {chunk_id}}}"

            formatted_chunk = f"{text} {citation}"
            formatted_results.append(formatted_chunk)

            logger.debug(f"Result {i + 1}: {document_name}, Score: {score:.3f}")

        return "\n\n".join(formatted_results)

    async def perform_query_expansion_retrieval(self, query: str,
                                                user_id: str,
                                                collection_ids: List[str],
                                                limit: int,
                                                dense_weight: float,
                                                normalization: str) -> List[Any]:
        """
        Perform retrieval with query expansion.

        Args:
            query: Original user query
            user_id: User ID for filtering
            collection_ids: Collections to search
            limit: Maximum results
            dense_weight: Weight for dense scores
            normalization: Score normalization method

        Returns:
            Formatted results string
        """
        logger.info(f"Starting query expansion retrieval for: '{query}'")

        # Generate query variants
        query_variants = await self.generate_query_variants(query)
        all_queries = [query] + query_variants

        # Perform retrieval for each query variant
        results_by_query = []

        for query_text in all_queries:
            query_results = await self.hybrid_search_service.perform_hybrid_search(
                query=query_text,
                collection_ids=collection_ids,
                user_id=user_id,
                limit=limit,
                dense_weight=dense_weight,
                normalization=normalization
            )
            results_by_query.append(query_results)

        fused_results = self.fusion_service.fuse_query_variants(results_by_query, method=EXPANSION_FUSION_METHOD)

        # Take top results and convert back to expected format
        top_results = [result for result, score in fused_results[:limit]]

        logger.info(f"Query expansion completed: {len(top_results)} final results")
        return top_results

    async def generate_query_variants(self, original_query: str, max_variants: int = None) -> List[str]:
        """
        Generate multiple query variants using LLM-based paraphrasing.

        Args:
            original_query: The original user query
            max_variants: Maximum number of variants to generate (uses config default if None)

        Returns:
            List of query variants (excluding the original query)
        """
        if max_variants is None:
            max_variants = MAX_QUERY_VARIANTS

        expansion_prompt = self._build_expansion_prompt(original_query, max_variants)

        try:
            start_time = time.time()
            response = await self.llm_client.ainvoke([{"role": "user", "content": expansion_prompt}])
            expansion_time = time.time() - start_time

            # Parse response to extract variants
            variants = self._parse_variants_response(response.content, original_query, max_variants)

            # Update metrics
            self._update_expansion_metrics(len(variants), expansion_time, success=True)

            logger.info(f"Generated {variants} query variants for '{original_query}' in {expansion_time:.2f}s")
            logger.debug(f"Query variants: {variants}")

            return variants

        except Exception as e:
            logger.error(f"Failed to generate query variants: {e}")
            self._update_expansion_metrics(0, 0, success=False)
            return []

    def _build_expansion_prompt(self, original_query: str, max_variants: int) -> str:
        """Build the LLM prompt for query expansion."""
        return f"""You are a query expansion expert. Generate {max_variants} alternative formulations of the following search query.
        Each variant should:
        1. Preserve the original intent and meaning
        2. Use different vocabulary, synonyms, or phrasing
        3. Be suitable for document retrieval
        4. Cover potential terminology variations
        5. Be concise and focused

        Guidelines:
        - Use domain-appropriate synonyms (e.g., "revenue" → "income", "sales", "earnings")
        - Rephrase questions in different styles (direct vs analytical)
        - Consider both formal and informal terminology
        - Avoid overly complex or lengthy reformulations

        Original query: "{original_query}"

        Generate {max_variants} query variants, one per line, without numbering or bullets:"""

    def _parse_variants_response(self, response_text: str, original_query: str, max_variants: int) -> List[str]:
        """Parse LLM response to extract clean query variants."""
        variants = []
        response_text = response_text.strip()

        for line in response_text.split('\n'):
            variant = line.strip().strip('"').strip("'").strip()

            if (variant
                    and variant != original_query
                    and len(variant) > 5
                    and variant not in variants
                    and not variant.lower().startswith(('generate', 'alternative', 'variant'))):
                variants.append(variant)

        return variants[:max_variants]

    def _update_expansion_metrics(self, variants_count: int, expansion_time: float, success: bool):
        """Update global expansion metrics."""
        global expansion_metrics

        expansion_metrics["queries_expanded"] += 1
        expansion_metrics["variants_generated"] += variants_count
        expansion_metrics["total_expansion_time"] += expansion_time

        if success:
            expansion_metrics["successful_expansions"] += 1
        else:
            expansion_metrics["failed_expansions"] += 1

        # Update average expansion time
        if expansion_metrics["successful_expansions"] > 0:
            expansion_metrics["average_expansion_time"] = (
                    expansion_metrics["total_expansion_time"] / expansion_metrics["successful_expansions"]
            )


class ResultDeduplicator:
    """
    Handles deduplication of search results across query variants.

    Removes duplicate documents/chunks that appear in multiple query variant results,
    keeping the highest-scoring instance of each unique item.
    """

    @staticmethod
    def create_chunk_hash(result: Any) -> str:
        """
        Create a unique hash for a search result chunk.

        Uses document_id + chunk_id or document_id + page_number as unique identifier.

        Args:
            result: Search result object with payload containing metadata

        Returns:
            MD5 hash string representing the unique chunk identifier
        """
        doc_id = result.payload.get('document_id', '')
        chunk_id = result.payload.get('chunk_id', '')
        page_number = result.payload.get('page_number', '')

        # Primary identifier: document_id + chunk_id
        primary_id = f"{doc_id}_{chunk_id}"

        # Fallback identifier: document_id + page_number
        fallback_id = f"{doc_id}_{page_number}"

        # Use primary if chunk_id exists, otherwise use fallback
        unique_id = primary_id if chunk_id else fallback_id

        return hashlib.md5(unique_id.encode()).hexdigest()

    @staticmethod
    def deduplicate_results(all_results: List[Tuple[Any, str, int]]) -> List[Tuple[Any, str, int]]:
        """
        Deduplicate results across query variants.

        Args:
            all_results: List of (result, variant_query, variant_index) tuples

        Returns:
            Deduplicated list of results with highest scoring instance kept
        """
        chunk_map = {}

        for result, variant_query, variant_index in all_results:
            chunk_hash = ResultDeduplicator.create_chunk_hash(result)

            if chunk_hash not in chunk_map:
                chunk_map[chunk_hash] = (result, variant_query, variant_index)
            else:
                # Keep the result with higher score
                existing_result, existing_query, existing_index = chunk_map[chunk_hash]
                if result.score > existing_result.score:
                    chunk_map[chunk_hash] = (result, variant_query, variant_index)

        deduplicated = list(chunk_map.values())

        # Update metrics
        original_count = len(all_results)
        deduplicated_count = len(deduplicated)
        expansion_metrics["deduplication_savings"] += (original_count - deduplicated_count)

        logger.info(f"Deduplication: {original_count} → {deduplicated_count} results "
                    f"(removed {original_count - deduplicated_count} duplicates)")

        return deduplicated



def get_expansion_metrics() -> Dict[str, Any]:
    # Calculate derived metrics
    total_queries = expansion_metrics["queries_expanded"]
    success_rate = (expansion_metrics["successful_expansions"] / total_queries * 100) if total_queries > 0 else 0
    avg_variants_per_query = (expansion_metrics["variants_generated"] / expansion_metrics["successful_expansions"]) if \
        expansion_metrics["successful_expansions"] > 0 else 0

    return {
        "performance_metrics": {
            **dict(expansion_metrics),
            "success_rate_percent": round(success_rate, 2),
            "average_variants_per_query": round(avg_variants_per_query, 2)
        }
    }


def reset_expansion_metrics():
    """Reset expansion metrics (useful for testing)."""
    global expansion_metrics
    expansion_metrics = {
        "queries_expanded": 0,
        "variants_generated": 0,
        "deduplication_savings": 0,
        "average_expansion_time": 0.0,
        "fusion_method_usage": defaultdict(int),
        "total_expansion_time": 0.0,
        "successful_expansions": 0,
        "failed_expansions": 0
    }
    logger.info("Expansion metrics reset")