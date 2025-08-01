import os
import hashlib
import time
import logging
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from langchain_openai import AzureChatOpenAI

logger = logging.getLogger(__name__)


ENABLE_QUERY_EXPANSION = os.getenv("ENABLE_QUERY_EXPANSION", "false").lower() == "true"
MAX_QUERY_VARIANTS = int(os.getenv("MAX_QUERY_VARIANTS", "3"))
EXPANSION_FUSION_METHOD = os.getenv("EXPANSION_FUSION_METHOD", "rrf")  # rrf, weighted, max_score
EXPANSION_TEMPERATURE = float(os.getenv("EXPANSION_TEMPERATURE", "0.3"))
EXPANSION_MAX_TOKENS = int(os.getenv("EXPANSION_MAX_TOKENS", "500"))

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


class QueryExpansionService:
    """
    Handles generation of query variants for improved retrieval coverage.

    This service uses LLM-based paraphrasing to generate alternative formulations
    of user queries, helping bridge vocabulary gaps between user language and
    document terminology.
    """

    def __init__(self, llm_client: AzureChatOpenAI):
        self.llm_client = llm_client

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


class ScoreFusionService:
    """
    Handles fusion of scores across query variants.

    Implements multiple fusion strategies to combine retrieval results from
    different query formulations into a unified ranked list.
    """

    @staticmethod
    def reciprocal_rank_fusion(results_by_variant: List[List[Any]], k: int = 60) -> List[Tuple[Any, float]]:
        """
        Apply Reciprocal Rank Fusion across query variants.

        RRF Score = Σ(1 / (rank_i + k)) for each variant where document appears

        Args:
            results_by_variant: List of result lists, one per query variant
            k: RRF parameter (default 60, commonly used value)

        Returns:
            List of (result_object, fused_score) tuples sorted by score
        """
        # Create document to RRF score mapping
        doc_scores = defaultdict(float)
        doc_objects = {}

        for variant_results in results_by_variant:
            for rank, result in enumerate(variant_results):
                chunk_hash = ResultDeduplicator.create_chunk_hash(result)
                rrf_score = 1.0 / (rank + 1 + k)
                doc_scores[chunk_hash] += rrf_score
                doc_objects[chunk_hash] = result

        # Convert to list and sort by RRF score
        fused_results = [(doc_objects[doc_hash], score)
                         for doc_hash, score in doc_scores.items()]
        fused_results.sort(key=lambda x: x[1], reverse=True)

        logger.debug(f"RRF fusion: {len(fused_results)} unique documents across {len(results_by_variant)} variants")
        return fused_results

    @staticmethod
    def weighted_score_fusion(results_by_variant: List[List[Any]],
                              variant_weights: Optional[List[float]] = None) -> List[Tuple[Any, float]]:
        """
        Apply weighted score fusion across query variants.

        Final Score = Σ(weight_i × normalized_score_i) for each variant

        Args:
            results_by_variant: List of result lists, one per query variant
            variant_weights: Weights for each variant (default: equal weights)

        Returns:
            List of (result_object, fused_score) tuples sorted by score
        """
        if variant_weights is None:
            variant_weights = [1.0] * len(results_by_variant)

        # Normalize scores within each variant
        normalized_variants = []
        for variant_results in results_by_variant:
            if not variant_results:
                normalized_variants.append([])
                continue

            scores = [r.score for r in variant_results]
            max_score = max(scores) if scores else 1.0
            min_score = min(scores) if scores else 0.0
            score_range = max_score - min_score if max_score != min_score else 1.0

            normalized_results = []
            for result in variant_results:
                normalized_score = (result.score - min_score) / score_range
                normalized_results.append((result, normalized_score))

            normalized_variants.append(normalized_results)

        doc_scores = defaultdict(float)
        doc_objects = {}

        for variant_idx, variant_results in enumerate(normalized_variants):
            weight = variant_weights[variant_idx]
            for result, normalized_score in variant_results:
                chunk_hash = ResultDeduplicator.create_chunk_hash(result)
                doc_scores[chunk_hash] += weight * normalized_score
                doc_objects[chunk_hash] = result

        fused_results = [(doc_objects[doc_hash], score)
                         for doc_hash, score in doc_scores.items()]
        fused_results.sort(key=lambda x: x[1], reverse=True)

        logger.debug(f"Weighted fusion: {len(fused_results)} unique documents with weights {variant_weights}")
        return fused_results

    @staticmethod
    def max_score_fusion(results_by_variant: List[List[Any]]) -> List[Tuple[Any, float]]:
        """
        Apply max score fusion - take highest score for each document across variants.

        Args:
            results_by_variant: List of result lists, one per query variant

        Returns:
            List of (result_object, max_score) tuples sorted by score
        """
        doc_scores = {}
        doc_objects = {}

        for variant_results in results_by_variant:
            for result in variant_results:
                chunk_hash = ResultDeduplicator.create_chunk_hash(result)
                if chunk_hash not in doc_scores or result.score > doc_scores[chunk_hash]:
                    doc_scores[chunk_hash] = result.score
                    doc_objects[chunk_hash] = result

        # Convert to list and sort
        fused_results = [(doc_objects[doc_hash], score)
                         for doc_hash, score in doc_scores.items()]
        fused_results.sort(key=lambda x: x[1], reverse=True)

        logger.debug(f"Max score fusion: {len(fused_results)} unique documents")
        return fused_results

    @staticmethod
    def apply_fusion(results_by_variant: List[List[Any]],
                     method: str = None,
                     variant_weights: Optional[List[float]] = None) -> List[Tuple[Any, float]]:
        """
        Apply the specified fusion method to results across variants.

        Args:
            results_by_variant: List of result lists, one per query variant
            method: Fusion method ("rrf", "weighted", "max_score")
            variant_weights: Weights for weighted fusion

        Returns:
            List of (result_object, fused_score) tuples sorted by score
        """
        if method is None:
            method = EXPANSION_FUSION_METHOD

        # Update metrics
        expansion_metrics["fusion_method_usage"][method] += 1

        logger.info(f"Applying {method} fusion across {len(results_by_variant)} query variants")

        if method == "rrf":
            return ScoreFusionService.reciprocal_rank_fusion(results_by_variant)
        elif method == "weighted":
            return ScoreFusionService.weighted_score_fusion(results_by_variant, variant_weights)
        elif method == "max_score":
            return ScoreFusionService.max_score_fusion(results_by_variant)
        else:
            logger.warning(f"Unknown fusion method: {method}, using RRF")
            return ScoreFusionService.reciprocal_rank_fusion(results_by_variant)


def get_expansion_config() -> Dict[str, Any]:
    """Get current query expansion configuration."""
    return {
        "enabled": ENABLE_QUERY_EXPANSION,
        "max_variants": MAX_QUERY_VARIANTS,
        "fusion_method": EXPANSION_FUSION_METHOD,
        "temperature": EXPANSION_TEMPERATURE,
        "max_tokens": EXPANSION_MAX_TOKENS
    }


def get_expansion_metrics() -> Dict[str, Any]:
    """Get query expansion performance metrics."""
    config = get_expansion_config()

    # Calculate derived metrics
    total_queries = expansion_metrics["queries_expanded"]
    success_rate = (expansion_metrics["successful_expansions"] / total_queries * 100) if total_queries > 0 else 0
    avg_variants_per_query = (expansion_metrics["variants_generated"] / expansion_metrics["successful_expansions"]) if \
    expansion_metrics["successful_expansions"] > 0 else 0

    return {
        "configuration": config,
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