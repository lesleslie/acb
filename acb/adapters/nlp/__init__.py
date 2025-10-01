"""Natural Language Processing (NLP) Adapters.

This package provides NLP adapters for various frameworks including spaCy and
Hugging Face Transformers. All adapters follow the ACB adapter pattern with
standardized interfaces for text analysis, sentiment analysis, named entity
recognition, and other NLP tasks.

Supported Frameworks:
    - spaCy: Industrial-strength NLP with comprehensive linguistic analysis
    - Transformers: Modern transformer-based models from Hugging Face

Usage:
    from acb.adapters import import_adapter

    # Import NLP adapter (dynamic selection based on settings)
    NLP = import_adapter("nlp")

    # Or import specific implementation
    from acb.adapters.nlp.spacy import SpacyNLP
    from acb.adapters.nlp.transformers import TransformersNLP

Configuration:
    Configure NLP framework in settings/adapters.yml:

    nlp: spacy          # or transformers

    Adapter-specific settings go in adapter settings files.

Features:
    - Async-first design with batch processing support
    - Standardized text analysis interface across frameworks
    - Sentiment analysis with confidence scores
    - Named entity recognition with entity type filtering
    - Language detection and keyword extraction
    - Text similarity calculation
    - Comprehensive error handling and health checking

All adapters implement the BaseNLPAdapter interface providing:
    - Text analysis (comprehensive multi-task processing)
    - Sentiment analysis with standardized labels
    - Named entity recognition with configurable types
    - Language detection and translation
    - Text classification with custom labels
    - Keyword extraction and text similarity
    - Batch processing for multiple texts
    - Health checking and connection management
"""

from __future__ import annotations

from acb.adapters.nlp._base import (
    BaseNLPAdapter,
    ClassificationResult,
    EntityType,
    KeywordResult,
    LanguageDetectionResult,
    NamedEntity,
    NLPSettings,
    SentimentLabel,
    SentimentResult,
    SimilarityResult,
    TaskType,
    TranslationResult,
)

# Import implementations with error handling
try:
    from acb.adapters.nlp.spacy import SpacyNLP, SpacyNLPSettings
except ImportError:
    SpacyNLP = None
    SpacyNLPSettings = None

try:
    from acb.adapters.nlp.transformers import TransformersNLP, TransformersNLPSettings
except ImportError:
    TransformersNLP = None
    TransformersNLPSettings = None

# Export all available classes
__all__ = [
    # Base classes
    "BaseNLPAdapter",
    "ClassificationResult",
    "EntityType",
    "KeywordResult",
    "LanguageDetectionResult",
    "NLPSettings",
    "NamedEntity",
    "SentimentLabel",
    "SentimentResult",
    "SimilarityResult",
    # spaCy
    "SpacyNLP",
    "SpacyNLPSettings",
    "TaskType",
    # Transformers
    "TransformersNLP",
    "TransformersNLPSettings",
    "TranslationResult",
]

# Create mapping for dynamic adapter loading
NLP_ADAPTERS = {}

if SpacyNLP:
    NLP_ADAPTERS["spacy"] = SpacyNLP

if TransformersNLP:
    NLP_ADAPTERS["transformers"] = TransformersNLP


def get_nlp_adapter(provider: str) -> type[BaseNLPAdapter] | None:
    """Get NLP adapter class by provider name.

    Args:
        provider: Provider name (spacy, transformers)

    Returns:
        Adapter class or None if not available
    """
    return NLP_ADAPTERS.get(provider.lower())


def list_available_providers() -> list[str]:
    """List available NLP providers.

    Returns:
        List of available provider names
    """
    return list(NLP_ADAPTERS.keys())
