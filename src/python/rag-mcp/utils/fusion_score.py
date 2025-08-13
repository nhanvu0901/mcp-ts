import logging
import numpy as np
import hashlib
from typing import List, Any, Tuple, Optional
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class NormalizationMethod(Enum):
    """Supported score normalization methods"""
    MIN_MAX = "min_max"

class FusionMethod(Enum):
    """Supported fusion methods"""
    WEIGHTED = "weighted"
    RRF = "reciprocal_rank_fusion"
    MAX_SCORE = "max_score"


class FusionService:
    """
    Unified fusion service for combining search results from different sources.

    Handles two main use cases:
    1. Dense + Sparse fusion (different search methods, same query)
    2. Query variant fusion (same search method, different queries)
    """

    def __init__(self, default_dense_weight: float = 0.6):
        self.default_dense_weight = default_dense_weight

    def normalize_scores(self, scores: List[float], method: NormalizationMethod = NormalizationMethod.MIN_MAX) -> List[float]:
        """
        Normalize scores using specified method.

        Args:
            scores: List of raw scores
            method: Normalization method to use

        Returns:
            List of normalized scores
        """
        if not scores:
            return []

        scores_array = np.array(scores)

        if method == NormalizationMethod.MIN_MAX:
            if scores_array.max() == scores_array.min():
                return [1.0] * len(scores)
            return ((scores_array - scores_array.min()) / (scores_array.max() - scores_array.min())).tolist()
        else:
            logger.warning(f"Unknown normalization method: {method}, using min-max")
            return self.normalize_scores(scores, NormalizationMethod.MIN_MAX)

    def create_result_hash(self, result: Any) -> str:
        """
        Create a unique hash for a search result.

        Args:
            result: Search result object

        Returns:
            MD5 hash string representing the unique result identifier
        """
        doc_id = result.payload.get('document_id', '')
        chunk_id = result.payload.get('chunk_id', '')
        page_number = result.payload.get('page_number', '')

        # Primary identifier: document_id + chunk_id
        primary_id = f"{doc_id}_{chunk_id}"
        # Fallback identifier: document_id + page_number
        fallback_id = f"{doc_id}_{page_number}"

        unique_id = primary_id if chunk_id is not None else fallback_id
        return hashlib.md5(unique_id.encode()).hexdigest()

    def weighted_fusion(self,
                        result_groups: List[List[Any]],
                        weights: Optional[List[float]] = None,
                        normalization: NormalizationMethod = NormalizationMethod.MIN_MAX) -> List[Any]:
        """
        Combine result groups using weighted fusion.

        Args:
            result_groups: List of result lists to combine
            weights: Weights for each group (defaults to equal weights)
            normalization: Score normalization method

        Returns:
            Combined and sorted results
        """
        if not result_groups or not any(result_groups):
            return []

        if weights is None:
            weights = [1.0] * len(result_groups)

        if len(weights) != len(result_groups):
            logger.warning(f"Weight count mismatch: {len(weights)} weights for {len(result_groups)} groups")
            weights = [1.0] * len(result_groups)

        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # Create result mappings
        result_scores = defaultdict(float)
        result_objects = {}

        for group_idx, results in enumerate(result_groups):
            if not results:
                continue

            # Extract and normalize scores
            scores = [getattr(r, 'score', 0) for r in results]
            normalized_scores = self.normalize_scores(scores, normalization)

            weight = weights[group_idx]

            for result, norm_score in zip(results, normalized_scores):
                result_hash = self.create_result_hash(result)
                result_scores[result_hash] += weight * norm_score
                result_objects[result_hash] = result

        # Create final results
        final_results = []
        for result_hash, final_score in result_scores.items():
            result_obj = result_objects[result_hash]
            result_obj.score = final_score
            final_results.append(result_obj)

        # Sort by score descending
        final_results.sort(key=lambda x: x.score, reverse=True)

        logger.debug(f"Weighted fusion: {sum(len(g) for g in result_groups)} → {len(final_results)} results")
        return final_results

    def reciprocal_rank_fusion(self,
                               result_groups: List[List[Any]],
                               k: int = 60) -> List[Any]:
        """
        Apply Reciprocal Rank Fusion across result groups.

        RRF Score = Σ(1 / (rank_i + k)) for each group where document appears

        Args:
            result_groups: List of result lists to combine
            k: RRF parameter (default 60)

        Returns:
            Combined results sorted by RRF score
        """
        if not result_groups or not any(result_groups):
            return []

        # Create result mappings
        rrf_scores = defaultdict(float)
        result_objects = {}

        for results in result_groups:
            for rank, result in enumerate(results):
                result_hash = self.create_result_hash(result)
                rrf_score = 1.0 / (rank + 1 + k)
                rrf_scores[result_hash] += rrf_score
                result_objects[result_hash] = result

        # Create final results
        final_results = []
        for result_hash, rrf_score in rrf_scores.items():
            result_obj = result_objects[result_hash]
            result_obj.score = rrf_score
            final_results.append(result_obj)

        # Sort by RRF score descending
        final_results.sort(key=lambda x: x.score, reverse=True)

        logger.debug(f"RRF fusion: {sum(len(g) for g in result_groups)} → {len(final_results)} results")
        return final_results



    def fuse_results(self,
                     result_groups: List[List[Any]],
                     method: FusionMethod = FusionMethod.WEIGHTED,
                     weights: Optional[List[float]] = None,
                     normalization: NormalizationMethod = NormalizationMethod.MIN_MAX,
                     **kwargs) -> List[Any]:
        """
        Apply specified fusion method to combine result groups.

        Args:
            result_groups: List of result lists to combine
            method: Fusion method to use
            weights: Weights for each group (weighted fusion only)
            normalization: Score normalization method
            **kwargs: Additional parameters (e.g., rrf_k for RRF)

        Returns:
            Combined and sorted results
        """
        if method == FusionMethod.WEIGHTED:
            return self.weighted_fusion(result_groups, weights, normalization)

        elif method == FusionMethod.RRF:
            k = kwargs.get('rrf_k', 60)
            return self.reciprocal_rank_fusion(result_groups, k)
        else:
            logger.warning(f"Unknown fusion method: {method}, using weighted fusion")
            return self.weighted_fusion(result_groups, weights, normalization)

    # Convenience methods for common use cases

    def fuse_dense_sparse(self,
                          dense_results: List[Any],
                          sparse_results: List[Any],
                          dense_weight: Optional[float] = None,
                          method: FusionMethod = FusionMethod.WEIGHTED,
                          normalization: NormalizationMethod = NormalizationMethod.MIN_MAX,
                          **kwargs) -> List[Any]:
        """
        Convenience method for fusing dense and sparse search results.

        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search
            dense_weight: Weight for dense scores (0.0-1.0)
            method: Fusion method
            normalization: Score normalization method
            **kwargs: Additional parameters

        Returns:
            Combined results
        """
        if dense_weight is None:
            dense_weight = self.default_dense_weight

        sparse_weight = 1.0 - dense_weight
        weights = [dense_weight, sparse_weight]

        return self.fuse_results(
            result_groups=[dense_results, sparse_results],
            method=method,
            weights=weights,
            normalization=normalization,
            **kwargs
        )

    def fuse_query_variants(self,
                            results_by_variant: List[List[Any]],
                            method: str = "rrf",
                            variant_weights: Optional[List[float]] = None,
                            **kwargs) -> List[Tuple[Any, float]]:
        """
        Convenience method for fusing results across query variants.
        Returns tuples of (result, score) for compatibility with existing code.

        Args:
            results_by_variant: List of result lists, one per query variant
            method: Fusion method ("rrf", "weighted", "max_score")
            variant_weights: Weights for each variant
            **kwargs: Additional parameters

        Returns:
            List of (result_object, fused_score) tuples sorted by score
        """
        if method == "rrf":
            fusion_method = FusionMethod.RRF
        elif method == "weighted":
            fusion_method = FusionMethod.WEIGHTED
        elif method == "max_score":
            fusion_method = FusionMethod.MAX_SCORE
        else:
            logger.warning(f"Unknown method: {method}, using RRF")
            fusion_method = FusionMethod.RRF

        fused_results = self.fuse_results(
            result_groups=results_by_variant,
            method=fusion_method,
            weights=variant_weights,
            **kwargs
        )

        # Convert to (result, score) tuples for compatibility
        return [(result, result.score) for result in fused_results]
