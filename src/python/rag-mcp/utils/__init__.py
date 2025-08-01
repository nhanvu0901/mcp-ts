from .query_expansion import (
    QueryExpansionService,
    ResultDeduplicator,
    ScoreFusionService,
    get_expansion_config,
    get_expansion_metrics,
    reset_expansion_metrics,
    ENABLE_QUERY_EXPANSION,
    MAX_QUERY_VARIANTS,
    EXPANSION_FUSION_METHOD
)

from .tfidf_search import TfidfService
from .dense_search import DenseSearchService
from .search_fusion_service import (
    SearchFusionService,
    NormalizationMethod,
    FusionMethod
)

__all__ = [
    # Query Expansion
    'QueryExpansionService',
    'ResultDeduplicator',
    'ScoreFusionService',
    'get_expansion_config',
    'get_expansion_metrics',
    'reset_expansion_metrics',
    'ENABLE_QUERY_EXPANSION',
    'MAX_QUERY_VARIANTS',
    'EXPANSION_FUSION_METHOD',

    'TfidfService',
    'DenseSearchService',
    'SearchFusionService',

    'NormalizationMethod',
    'FusionMethod'
]