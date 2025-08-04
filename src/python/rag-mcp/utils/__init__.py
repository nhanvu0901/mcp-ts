from .query_expansion import (
    QueryExpansionService,
    ResultDeduplicator,
    get_expansion_metrics,
    reset_expansion_metrics,
    ENABLE_QUERY_EXPANSION,
    MAX_QUERY_VARIANTS,
)

from .tfidf_search import TfidfService
from .dense_search import DenseSearchService
from .fusion_score import (
    FusionService,
    NormalizationMethod,
    FusionMethod,
)

__all__ = [
    # Query Expansion
    'QueryExpansionService',
    'ResultDeduplicator',
    'get_expansion_metrics',
    'reset_expansion_metrics',
    'ENABLE_QUERY_EXPANSION',
    'MAX_QUERY_VARIANTS',

    # Search Services
    'TfidfService',
    'DenseSearchService',

    # Fusion Services
    'FusionService',
    'NormalizationMethod',
    'FusionMethod',
]