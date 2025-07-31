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

__all__ = [
    'QueryExpansionService',
    'ResultDeduplicator',
    'ScoreFusionService',
    'get_expansion_config',
    'get_expansion_metrics',
    'reset_expansion_metrics',
    'ENABLE_QUERY_EXPANSION',
    'MAX_QUERY_VARIANTS',
    'EXPANSION_FUSION_METHOD'
]