"""spaCy NLP Adapter.

This adapter provides integration with spaCy for comprehensive natural language
processing tasks including sentiment analysis, named entity recognition, text
classification, and linguistic analysis with high performance and accuracy.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import Field
from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    generate_adapter_id,
)
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

try:
    import spacy
    from spacy.lang.en.stop_words import STOP_WORDS
    from spacy.tokens import Doc

    _spacy_available = True
except ImportError:
    spacy = None
    STOP_WORDS = set()
    Doc = None
    _spacy_available = False


MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="spaCy NLP",
    category="nlp",
    provider="spacy",
    version="1.0.0",
    acb_min_version="0.19.0",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.BATCH_OPERATIONS,
        AdapterCapability.TEXT_ANALYSIS,
        AdapterCapability.NAMED_ENTITY_RECOGNITION,
        AdapterCapability.LANGUAGE_DETECTION,
    ],
    required_packages=["spacy>=3.7.0"],
    description="High-performance spaCy NLP with comprehensive text analysis",
)


class SpacyNLPSettings(NLPSettings):
    """spaCy-specific NLP settings."""

    # Model settings
    model_name: str = Field(
        default="en_core_web_sm",
        description="spaCy model name",
    )
    enable_extensions: bool = Field(
        default=True,
        description="Enable spaCy extensions",
    )

    # Processing settings
    disable_components: list[str] = Field(
        default_factory=list,
        description="Components to disable for performance",
    )
    enable_gpu: bool = Field(
        default=False,
        description="Enable GPU acceleration",
    )

    # Sentiment analysis (requires textblob or spacytextblob)
    sentiment_model: str = Field(
        default="textblob",
        description="Sentiment analysis model (textblob, vader)",
    )

    # NER settings
    custom_ner_model: str | None = Field(
        default=None,
        description="Path to custom NER model",
    )

    # Classification settings
    classification_model: str | None = Field(
        default=None,
        description="Path to text classification model",
    )


class SpacyNLP(BaseNLPAdapter):
    """spaCy NLP adapter."""

    def __init__(self, settings: SpacyNLPSettings | None = None) -> None:
        """Initialize spaCy NLP adapter.

        Args:
            settings: spaCy-specific adapter settings
        """
        if not _spacy_available:
            msg = (
                "spaCy is required for SpacyNLP adapter. "
                "Install with: pip install spacy && python -m spacy download en_core_web_sm"
            )
            raise ImportError(
                msg,
            )

        super().__init__(settings)
        self._settings: SpacyNLPSettings = settings or SpacyNLPSettings()
        self._nlp = None

    async def connect(self) -> None:
        """Connect to spaCy (load models)."""
        await self._ensure_nlp()

    async def disconnect(self) -> None:
        """Disconnect from spaCy (unload models)."""
        self._nlp = None

    async def _ensure_nlp(self) -> None:
        """Ensure spaCy model is loaded."""
        if self._nlp is None:
            self._nlp = await self._create_nlp()
        return self._nlp

    async def _create_nlp(self) -> None:
        """Create spaCy NLP pipeline."""
        # Load model in thread pool to avoid blocking
        nlp = await self._run_sync(
            spacy.load,
            self._settings.model_name,
            disable=self._settings.disable_components,
        )

        # Enable GPU if requested
        if self._settings.enable_gpu:
            try:
                await self._run_sync(spacy.require_gpu)
            except Exception:
                pass  # GPU not available, continue with CPU

        # Add extensions if enabled
        if self._settings.enable_extensions:
            await self._add_extensions(nlp)

        return nlp

    async def _add_extensions(self: Any, nlp: Any) -> None:
        """Add spaCy extensions for additional functionality."""
        try:
            # Add sentiment extension if textblob is available
            if self._settings.sentiment_model == "textblob":
                try:
                    nlp.add_pipe("spacytextblob")
                except ImportError:
                    pass

        except Exception:
            pass  # Extensions not available

    async def _run_sync(self, func, *args, **kwargs) -> None:
        """Run synchronous function in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    async def health_check(self) -> bool:
        """Check spaCy health."""
        try:
            nlp = await self._ensure_nlp()
            # Test processing
            await self._run_sync(nlp, "test")
            return True
        except Exception:
            return False

    # Core NLP Tasks
    async def analyze_text(
        self,
        text: str,
        tasks: list[TaskType] | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Perform comprehensive text analysis."""
        nlp = await self._ensure_nlp()
        doc = await self._run_sync(nlp, text)

        results = {}

        # Default tasks if none specified
        if tasks is None:
            tasks = [
                TaskType.SENTIMENT_ANALYSIS,
                TaskType.NAMED_ENTITY_RECOGNITION,
                TaskType.KEYWORD_EXTRACTION,
                TaskType.LANGUAGE_DETECTION,
            ]

        # Perform requested tasks
        for task in tasks:
            if task == TaskType.SENTIMENT_ANALYSIS:
                results["sentiment"] = await self._extract_sentiment_from_doc(doc)
            elif task == TaskType.NAMED_ENTITY_RECOGNITION:
                results["entities"] = await self._extract_entities_from_doc(doc)
            elif task == TaskType.KEYWORD_EXTRACTION:
                results["keywords"] = await self._extract_keywords_from_doc(doc)
            elif task == TaskType.LANGUAGE_DETECTION:
                results["language"] = await self._detect_language_from_doc(doc)

        return results

    async def analyze_sentiment(
        self,
        text: str,
        language: str | None = None,
    ) -> SentimentResult:
        """Analyze sentiment using spaCy."""
        nlp = await self._ensure_nlp()
        doc = await self._run_sync(nlp, text)

        return await self._extract_sentiment_from_doc(doc)

    async def _extract_sentiment_from_doc(self: Any, doc: Any) -> SentimentResult:
        """Extract sentiment from spaCy doc."""
        # Try spacytextblob extension first
        if hasattr(doc._, "blob"):
            polarity = doc._.blob.polarity
            if polarity > 0.1:
                label = SentimentLabel.POSITIVE
            elif polarity < -0.1:
                label = SentimentLabel.NEGATIVE
            else:
                label = SentimentLabel.NEUTRAL

            confidence = abs(polarity)
            scores = {
                "positive": max(0, polarity),
                "negative": max(0, -polarity),
                "neutral": 1 - abs(polarity),
            }

        else:
            # Fallback to simple rule-based sentiment
            positive_words = {
                "good",
                "great",
                "excellent",
                "amazing",
                "wonderful",
                "fantastic",
                "love",
                "like",
            }
            negative_words = {
                "bad",
                "terrible",
                "awful",
                "hate",
                "horrible",
                "worst",
                "dislike",
            }

            tokens = [
                token.text.lower()
                for token in doc
                if not token.is_stop and not token.is_punct
            ]
            pos_count = sum(1 for token in tokens if token in positive_words)
            neg_count = sum(1 for token in tokens if token in negative_words)

            if pos_count > neg_count:
                label = SentimentLabel.POSITIVE
                confidence = min(0.8, pos_count / len(tokens) * 2)
            elif neg_count > pos_count:
                label = SentimentLabel.NEGATIVE
                confidence = min(0.8, neg_count / len(tokens) * 2)
            else:
                label = SentimentLabel.NEUTRAL
                confidence = 0.5

            scores = {
                "positive": pos_count / max(1, pos_count + neg_count),
                "negative": neg_count / max(1, pos_count + neg_count),
                "neutral": 0.5,
            }

        return SentimentResult(
            label=label,
            confidence=confidence,
            scores=scores,
        )

    async def extract_entities(
        self,
        text: str,
        entity_types: list[EntityType] | None = None,
        language: str | None = None,
    ) -> list[NamedEntity]:
        """Extract named entities using spaCy."""
        nlp = await self._ensure_nlp()
        doc = await self._run_sync(nlp, text)

        return await self._extract_entities_from_doc(doc, entity_types)

    async def _extract_entities_from_doc(
        self,
        doc,
        entity_types: list[EntityType] | None = None,
    ) -> list[NamedEntity]:
        """Extract entities from spaCy doc."""
        entities = []

        for ent in doc.ents:
            # Map spaCy labels to standard EntityType
            entity_label = self._map_spacy_label(ent.label_)

            # Filter by entity types if specified
            if entity_types and entity_label not in [et.value for et in entity_types]:
                continue

            entities.append(
                NamedEntity(
                    text=ent.text,
                    label=entity_label,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=1.0,  # spaCy doesn't provide confidence scores by default
                ),
            )

        return entities

    def _map_spacy_label(self, spacy_label: str) -> str:
        """Map spaCy entity labels to standard EntityType."""
        mapping = {
            "PERSON": EntityType.PERSON.value,
            "ORG": EntityType.ORGANIZATION.value,
            "GPE": EntityType.LOCATION.value,
            "LOC": EntityType.LOCATION.value,
            "MONEY": EntityType.MONEY.value,
            "DATE": EntityType.DATE.value,
            "TIME": EntityType.TIME.value,
            "PERCENT": EntityType.PERCENT.value,
            "FAC": EntityType.FACILITY.value,
            "PRODUCT": EntityType.PRODUCT.value,
            "EVENT": EntityType.EVENT.value,
            "WORK_OF_ART": EntityType.WORK_OF_ART.value,
            "LAW": EntityType.LAW.value,
            "LANGUAGE": EntityType.LANGUAGE.value,
        }
        return mapping.get(spacy_label, EntityType.MISCELLANEOUS.value)

    async def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str | None = None,
    ) -> TranslationResult:
        """Translate text (spaCy doesn't have built-in translation)."""
        # spaCy doesn't have built-in translation
        # This would need integration with external translation service
        msg = "Translation not available in base spaCy. Use a specialized translation adapter."
        raise NotImplementedError(
            msg,
        )

    async def classify_text(
        self,
        text: str,
        labels: list[str] | None = None,
        model: str | None = None,
    ) -> ClassificationResult:
        """Classify text using spaCy."""
        nlp = await self._ensure_nlp()

        # Check if text classification component is available
        if (
            "textcat" not in nlp.pipe_names
            and "textcat_multilabel" not in nlp.pipe_names
        ):
            msg = "Text classification component not available in spaCy model"
            raise NotImplementedError(
                msg,
            )

        doc = await self._run_sync(nlp, text)

        # Get classification scores
        scores = doc.cats
        if not scores:
            msg = "No classification scores available"
            raise ValueError(msg)

        # Find best label
        best_label = max(scores, key=scores.get)
        confidence = scores[best_label]

        return ClassificationResult(
            label=best_label,
            confidence=confidence,
            scores=scores,
        )

    async def detect_language(self, text: str) -> LanguageDetectionResult:
        """Detect language using spaCy."""
        nlp = await self._ensure_nlp()
        doc = await self._run_sync(nlp, text)

        return await self._detect_language_from_doc(doc)

    async def _detect_language_from_doc(self: Any, doc: Any) -> LanguageDetectionResult:
        """Detect language from spaCy doc."""
        # spaCy models are language-specific, so we know the language
        lang_info = doc.lang_

        # Map spaCy language codes
        lang_mapping = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "zh": "Chinese",
            "ja": "Japanese",
        }

        language = lang_mapping.get(lang_info, "Unknown")

        return LanguageDetectionResult(
            language=language,
            confidence=0.9,  # High confidence since model is language-specific
            iso_code=lang_info,
        )

    async def extract_keywords(
        self,
        text: str,
        max_keywords: int = 10,
        language: str | None = None,
    ) -> list[KeywordResult]:
        """Extract keywords using spaCy."""
        nlp = await self._ensure_nlp()
        doc = await self._run_sync(nlp, text)

        return await self._extract_keywords_from_doc(doc, max_keywords)

    async def _extract_keywords_from_doc(
        self,
        doc,
        max_keywords: int = 10,
    ) -> list[KeywordResult]:
        """Extract keywords from spaCy doc."""
        # Extract important tokens (nouns, adjectives, proper nouns)
        keywords = {}

        for token in doc:
            # Skip stop words, punctuation, spaces
            if (
                token.is_stop
                or token.is_punct
                or token.is_space
                or len(token.text) < 3
                or token.pos_ in ["DET", "PRON", "ADP", "CONJ", "PART"]
            ):
                continue

            # Focus on important parts of speech
            if token.pos_ in ["NOUN", "PROPN", "ADJ", "VERB"]:
                # Use lemma for normalization
                key = token.lemma_.lower()
                if key not in keywords:
                    keywords[key] = {
                        "text": token.text,
                        "count": 0,
                        "score": 0,
                    }
                keywords[key]["count"] += 1
                # Score based on POS and position
                pos_weight = {"PROPN": 3, "NOUN": 2, "ADJ": 1.5, "VERB": 1}.get(
                    token.pos_,
                    1,
                )
                keywords[key]["score"] += pos_weight

        # Sort by score and return top keywords
        sorted_keywords = sorted(
            keywords.items(),
            key=lambda x: x[1]["score"],
            reverse=True,
        )[:max_keywords]

        return [
            KeywordResult(
                keyword=data["text"],
                score=data["score"],
                frequency=data["count"],
            )
            for _, data in sorted_keywords
        ]

    async def calculate_similarity(
        self,
        text1: str,
        text2: str,
        method: str = "cosine",
    ) -> SimilarityResult:
        """Calculate similarity using spaCy."""
        nlp = await self._ensure_nlp()

        # Process both texts
        doc1 = await self._run_sync(nlp, text1)
        doc2 = await self._run_sync(nlp, text2)

        # Calculate similarity using spaCy's built-in similarity
        similarity = await self._run_sync(doc1.similarity, doc2)

        return SimilarityResult(
            similarity=float(similarity),
            method="spacy_vectors",
        )

    async def get_supported_tasks(self) -> list[TaskType]:
        """Get supported NLP tasks."""
        return [
            TaskType.TEXT_ANALYSIS,
            TaskType.SENTIMENT_ANALYSIS,
            TaskType.NAMED_ENTITY_RECOGNITION,
            TaskType.LANGUAGE_DETECTION,
            TaskType.KEYWORD_EXTRACTION,
            TaskType.TEXT_SIMILARITY,
        ]


# Create type alias for backward compatibility
NLP = SpacyNLP
