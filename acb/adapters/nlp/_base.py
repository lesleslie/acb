"""Base NLP Adapter.

This module provides the foundation for NLP adapters, including interfaces for
text analysis, sentiment analysis, named entity recognition, language translation,
and other natural language processing tasks across different NLP frameworks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SentimentLabel(str, Enum):
    """Sentiment analysis labels."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class EntityType(str, Enum):
    """Named entity types."""

    PERSON = "PERSON"
    ORGANIZATION = "ORG"
    LOCATION = "LOC"
    MISCELLANEOUS = "MISC"
    MONEY = "MONEY"
    DATE = "DATE"
    TIME = "TIME"
    PERCENT = "PERCENT"
    FACILITY = "FAC"
    PRODUCT = "PRODUCT"
    EVENT = "EVENT"
    WORK_OF_ART = "WORK_OF_ART"
    LAW = "LAW"
    LANGUAGE = "LANGUAGE"


class TaskType(str, Enum):
    """NLP task types."""

    TEXT_ANALYSIS = "text_analysis"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    NAMED_ENTITY_RECOGNITION = "named_entity_recognition"
    LANGUAGE_TRANSLATION = "language_translation"
    TEXT_CLASSIFICATION = "text_classification"
    QUESTION_ANSWERING = "question_answering"
    TEXT_SUMMARIZATION = "text_summarization"
    KEYWORD_EXTRACTION = "keyword_extraction"
    LANGUAGE_DETECTION = "language_detection"
    TEXT_SIMILARITY = "text_similarity"


class SentimentResult(BaseModel):
    """Sentiment analysis result."""

    model_config = ConfigDict(extra="allow")

    label: SentimentLabel
    confidence: float = Field(ge=0.0, le=1.0)
    scores: dict[str, float] = Field(default_factory=dict)


class NamedEntity(BaseModel):
    """Named entity recognition result."""

    model_config = ConfigDict(extra="allow")

    text: str
    label: str
    start: int
    end: int
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class TranslationResult(BaseModel):
    """Language translation result."""

    model_config = ConfigDict(extra="allow")

    text: str
    source_language: str | None = None
    target_language: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class ClassificationResult(BaseModel):
    """Text classification result."""

    model_config = ConfigDict(extra="allow")

    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    scores: dict[str, float] = Field(default_factory=dict)


class LanguageDetectionResult(BaseModel):
    """Language detection result."""

    model_config = ConfigDict(extra="allow")

    language: str
    confidence: float = Field(ge=0.0, le=1.0)
    iso_code: str | None = None


class KeywordResult(BaseModel):
    """Keyword extraction result."""

    model_config = ConfigDict(extra="allow")

    keyword: str
    score: float = Field(ge=0.0)
    frequency: int = Field(ge=0, default=1)


class SimilarityResult(BaseModel):
    """Text similarity result."""

    model_config = ConfigDict(extra="allow")

    similarity: float = Field(ge=0.0, le=1.0)
    method: str = "cosine"


class NLPSettings(BaseModel):
    """Base NLP adapter settings."""

    model_config = ConfigDict(extra="allow")

    # Model settings
    model_name: str | None = None
    model_path: str | None = None
    device: str = "cpu"  # cpu, cuda, mps

    # Processing settings
    max_length: int = 512
    batch_size: int = 32
    num_threads: int = 1

    # Language settings
    default_language: str = "en"
    supported_languages: list[str] = Field(default_factory=lambda: ["en"])

    # Performance settings
    cache_results: bool = True
    timeout: int = 30  # seconds


class BaseNLPAdapter(ABC):
    """Base class for NLP adapters."""

    def __init__(self, settings: NLPSettings | None = None) -> None:
        """Initialize the NLP adapter.

        Args:
            settings: Adapter configuration settings
        """
        self._settings = settings or NLPSettings()
        self._client = None
        self._models = {}

    @property
    def settings(self) -> NLPSettings:
        """Get adapter settings."""
        return self._settings

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    # Connection Management
    @abstractmethod
    async def connect(self) -> None:
        """Connect to NLP service or load models."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from NLP service or unload models."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the NLP service is healthy."""

    # Core NLP Tasks
    @abstractmethod
    async def analyze_text(
        self,
        text: str,
        tasks: list[TaskType] | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Perform comprehensive text analysis.

        Args:
            text: Input text to analyze
            tasks: List of NLP tasks to perform
            language: Text language (auto-detect if None)

        Returns:
            Dictionary with analysis results for each task
        """

    @abstractmethod
    async def analyze_sentiment(
        self,
        text: str,
        language: str | None = None,
    ) -> SentimentResult:
        """Analyze sentiment of text.

        Args:
            text: Input text
            language: Text language

        Returns:
            Sentiment analysis result
        """

    @abstractmethod
    async def extract_entities(
        self,
        text: str,
        entity_types: list[EntityType] | None = None,
        language: str | None = None,
    ) -> list[NamedEntity]:
        """Extract named entities from text.

        Args:
            text: Input text
            entity_types: Types of entities to extract
            language: Text language

        Returns:
            List of named entities
        """

    @abstractmethod
    async def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str | None = None,
    ) -> TranslationResult:
        """Translate text to target language.

        Args:
            text: Input text
            target_language: Target language code
            source_language: Source language code (auto-detect if None)

        Returns:
            Translation result
        """

    @abstractmethod
    async def classify_text(
        self,
        text: str,
        labels: list[str] | None = None,
        model: str | None = None,
    ) -> ClassificationResult:
        """Classify text into categories.

        Args:
            text: Input text
            labels: Possible classification labels
            model: Specific model to use

        Returns:
            Classification result
        """

    @abstractmethod
    async def detect_language(self, text: str) -> LanguageDetectionResult:
        """Detect language of text.

        Args:
            text: Input text

        Returns:
            Language detection result
        """

    @abstractmethod
    async def extract_keywords(
        self,
        text: str,
        max_keywords: int = 10,
        language: str | None = None,
    ) -> list[KeywordResult]:
        """Extract keywords from text.

        Args:
            text: Input text
            max_keywords: Maximum number of keywords
            language: Text language

        Returns:
            List of extracted keywords
        """

    @abstractmethod
    async def calculate_similarity(
        self,
        text1: str,
        text2: str,
        method: str = "cosine",
    ) -> SimilarityResult:
        """Calculate similarity between two texts.

        Args:
            text1: First text
            text2: Second text
            method: Similarity calculation method

        Returns:
            Similarity result
        """

    # Batch Processing
    async def analyze_sentiment_batch(
        self,
        texts: list[str],
        language: str | None = None,
    ) -> list[SentimentResult]:
        """Analyze sentiment for multiple texts.

        Args:
            texts: List of input texts
            language: Text language

        Returns:
            List of sentiment analysis results
        """
        results = []
        for text in texts:
            result = await self.analyze_sentiment(text, language)
            results.append(result)
        return results

    async def extract_entities_batch(
        self,
        texts: list[str],
        entity_types: list[EntityType] | None = None,
        language: str | None = None,
    ) -> list[list[NamedEntity]]:
        """Extract entities from multiple texts.

        Args:
            texts: List of input texts
            entity_types: Types of entities to extract
            language: Text language

        Returns:
            List of entity extraction results
        """
        results = []
        for text in texts:
            result = await self.extract_entities(text, entity_types, language)
            results.append(result)
        return results

    async def translate_text_batch(
        self,
        texts: list[str],
        target_language: str,
        source_language: str | None = None,
    ) -> list[TranslationResult]:
        """Translate multiple texts.

        Args:
            texts: List of input texts
            target_language: Target language code
            source_language: Source language code

        Returns:
            List of translation results
        """
        results = []
        for text in texts:
            result = await self.translate_text(text, target_language, source_language)
            results.append(result)
        return results

    # Utility Methods
    async def get_supported_languages(self) -> list[str]:
        """Get list of supported languages.

        Returns:
            List of supported language codes
        """
        return self._settings.supported_languages

    async def get_supported_tasks(self) -> list[TaskType]:
        """Get list of supported NLP tasks.

        Returns:
            List of supported task types
        """
        # Default implementation - subclasses should override
        return [
            TaskType.TEXT_ANALYSIS,
            TaskType.SENTIMENT_ANALYSIS,
            TaskType.NAMED_ENTITY_RECOGNITION,
            TaskType.LANGUAGE_DETECTION,
        ]
