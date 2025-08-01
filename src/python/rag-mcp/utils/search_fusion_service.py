import logging
import numpy as np
from typing import List, Any, Tuple, Dict
from enum import Enum

logger = logging.getLogger(__name__)


class NormalizationMethod(Enum):
    """Supported score normalization methods"""
    MIN_MAX = "min_max"
    Z_SCORE = "z_score"
    RECIPROCAL_RANK = "reciprocal_rank"
    NONE = "none"


class FusionMethod(Enum):
    """Supported fusion methods"""
    WEIGHTED = "weighted"
    RRF = "reciprocal_rank_fusion"
    MAX_SCORE = "max_score"


class SearchFusionService:
    """
    Handles fusion of dense and sparse search results.

    Combines results from different search methods using various
    normalization and fusion strategies.
    """

    def __init__(self, default_dense_weight: float = 0.6):
        self.default_dense_weight = default_dense_weight

    def normalize_scores(self, scores: List[float], method: NormalizationMethod = NormalizationMethod.MIN_MAX) -> List[
        float]:
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

        elif method == NormalizationMethod.Z_SCORE:
            if scores_array.std() == 0:
                return [1.0] * len(scores)
            return ((scores_array - scores_array.mean()) / scores_array.std()).tolist()

        elif method == NormalizationMethod.RECIPROCAL_RANK:
            # Convert to ranks (1 = highest score)
            ranks = np.argsort(np.argsort(-scores_array)) + 1
            return (1.0 / ranks).tolist()

        elif method == NormalizationMethod.NONE:
            return scores

        else:
            logger.warning(f"Unknown normalization method: {method}, using min-max")
            return self.normalize_scores(scores, NormalizationMethod.MIN_MAX)

    def weighted_fusion(self,
                        dense_results: List[Any],
                        sparse_results: List[Any],
                        dense_weight: float = None,
                        normalization: NormalizationMethod = NormalizationMethod.MIN_MAX) -> List[Any]:
        """
        Combine dense and sparse results using weighted fusion.

        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search
            dense_weight: Weight for dense scores (0.0-1.0)
            normalization: Score normalization method

        Returns:
            Combined and sorted results
        """
        if dense_weight is None:
            dense_weight = self.default_dense_weight

        sparse_weight = 1.0 - dense_weight

        if not dense_results and not sparse_results:
            return []

        # Extract and normalize scores
        dense_scores = self.normalize_scores(
            [getattr(r, 'score', 0) for r in dense_results],
            normalization
        )
        sparse_scores = self.normalize_scores(
            [getattr(r, 'score', 0) for r in sparse_results],
            normalization
        )

        # Create score mapping by point ID
        dense_map = {r.id: (score, r) for r, score in zip(dense_results, dense_scores)}
        sparse_map = {r.id: (score, r) for r, score in zip(sparse_results, sparse_scores)}

        # Combine scores
        combined_results = []
        all_ids = set(dense_map.keys()) | set(sparse_map.keys())

        for point_id in all_ids:
            dense_score, dense_result = dense_map.get(point_id, (0.0, None))
            sparse_score, sparse_result = sparse_map.get(point_id, (0.0, None))

            # Use result object from whichever search found it
            result_obj = dense_result or sparse_result

            # Calculate weighted fusion score
            final_score = dense_weight * dense_score + sparse_weight * sparse_score

            # Update result object with fused score
            result_obj.score = final_score
            combined_results.append(result_obj)

        # Sort by fused score descending
        combined_results.sort(key=lambda x: x.score, reverse=True)

        logger.debug(
            f"Weighted fusion: {len(dense_results)} dense + {len(sparse_results)} sparse → {len(combined_results)} combined")
        return combined_results

    def reciprocal_rank_fusion(self,
                               dense_results: List[Any],
                               sparse_results: List[Any],
                               k: int = 60) -> List[Any]:
        """
        Apply Reciprocal Rank Fusion (RRF) to combine results.

        RRF Score = 1/(rank_dense + k) + 1/(rank_sparse + k)

        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search
            k: RRF parameter (typically 60)

        Returns:
            Combined results sorted by RRF score
        """
        if not dense_results and not sparse_results:
            return []

        # Create rank mappings
        dense_ranks = {r.id: rank + 1 for rank, r in enumerate(dense_results)}
        sparse_ranks = {r.id: rank + 1 for rank, r in enumerate(sparse_results)}

        # Create result object mapping
        all_results = {}
        for r in dense_results + sparse_results:
            all_results[r.id] = r

        # Calculate RRF scores
        rrf_scores = {}
        all_ids = set(dense_ranks.keys()) | set(sparse_ranks.keys())

        for doc_id in all_ids:
            dense_rank = dense_ranks.get(doc_id, float('inf'))
            sparse_rank = sparse_ranks.get(doc_id, float('inf'))

            rrf_score = 0.0
            if dense_rank != float('inf'):
                rrf_score += 1.0 / (dense_rank + k)
            if sparse_rank != float('inf'):
                rrf_score += 1.0 / (sparse_rank + k)

            rrf_scores[doc_id] = rrf_score

        # Create final results with RRF scores
        final_results = []
        for doc_id, rrf_score in rrf_scores.items():
            result_obj = all_results[doc_id]
            result_obj.score = rrf_score
            final_results.append(result_obj)

        # Sort by RRF score descending
        final_results.sort(key=lambda x: x.score, reverse=True)

        logger.debug(
            f"RRF fusion: {len(dense_results)} dense + {len(sparse_results)} sparse → {len(final_results)} combined")
        return final_results

    def max_score_fusion(self,
                         dense_results: List[Any],
                         sparse_results: List[Any]) -> List[Any]:
        """
        Combine results by taking maximum score for each document.

        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search

        Returns:
            Combined results with max scores
        """
        if not dense_results and not sparse_results:
            return []

        # Create score and result mappings
        doc_scores = {}
        doc_results = {}

        for result in dense_results + sparse_results:
            doc_id = result.id
            score = getattr(result, 'score', 0)

            if doc_id not in doc_scores or score > doc_scores[doc_id]:
                doc_scores[doc_id] = score
                doc_results[doc_id] = result

        # Create final results
        final_results = []
        for doc_id, max_score in doc_scores.items():
            result_obj = doc_results[doc_id]
            result_obj.score = max_score
            final_results.append(result_obj)

        # Sort by max score descending
        final_results.sort(key=lambda x: x.score, reverse=True)

        logger.debug(
            f"Max score fusion: {len(dense_results)} dense + {len(sparse_results)} sparse → {len(final_results)} combined")
        return final_results

    def fuse_results(self,
                     dense_results: List[Any],
                     sparse_results: List[Any],
                     method: FusionMethod = FusionMethod.WEIGHTED,
                     dense_weight: float = None,
                     normalization: NormalizationMethod = NormalizationMethod.MIN_MAX,
                     **kwargs) -> List[Any]:
        """
        Apply specified fusion method to combine search results.

        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search
            method: Fusion method to use
            dense_weight: Weight for dense scores (weighted fusion only)
            normalization: Score normalization method
            **kwargs: Additional parameters for specific fusion methods

        Returns:
            Combined and sorted results
        """
        if method == FusionMethod.WEIGHTED:
            return self.weighted_fusion(
                dense_results, sparse_results, dense_weight, normalization
            )

        elif method == FusionMethod.RRF:
            k = kwargs.get('rrf_k', 60)
            return self.reciprocal_rank_fusion(dense_results, sparse_results, k)

        elif method == FusionMethod.MAX_SCORE:
            return self.max_score_fusion(dense_results, sparse_results)

        else:
            logger.warning(f"Unknown fusion method: {method}, using weighted fusion")
            return self.weighted_fusion(
                dense_results, sparse_results, dense_weight, normalization
            )