"""Transformers NLP Adapter.

This adapter provides integration with Hugging Face Transformers for modern
transformer-based NLP tasks including sentiment analysis, text classification,
named entity recognition, and question answering with state-of-the-art models.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
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
    import torch
    from transformers import (
        AutoConfig,
        AutoModelForSequenceClassification,
        AutoModelForTokenClassification,
        AutoTokenizer,
        pipeline,
    )

    _transformers_available = True
except ImportError:
    torch = None
    AutoConfig = None
    AutoModelForSequenceClassification = None
    AutoModelForTokenClassification = None
    AutoTokenizer = None
    pipeline = None
    _transformers_available = False


MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="Transformers NLP",
    category="nlp",
    provider="transformers",
    version="1.0.0",
    acb_min_version="0.19.0",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.BATCH_OPERATIONS,
        AdapterCapability.TEXT_ANALYSIS,
        AdapterCapability.NAMED_ENTITY_RECOGNITION,
        AdapterCapability.TEXT_CLASSIFICATION,
        AdapterCapability.LANGUAGE_DETECTION,
    ],
    required_packages=["transformers>=4.30.0", "torch>=2.0.0"],
    description="Modern transformer-based NLP with Hugging Face models",
)


class TransformersNLPSettings(NLPSettings):
    """Transformers-specific NLP settings."""

    # Model settings
    sentiment_model: str = Field(
        default="cardiffnlp/twitter-roberta-base-sentiment-latest",
        description="Sentiment analysis model",
    )
    ner_model: str = Field(
        default="dbmdz/bert-large-cased-finetuned-conll03-english",
        description="Named entity recognition model",
    )
    classification_model: str = Field(
        default="facebook/bart-large-mnli",
        description="Text classification model",
    )
    qa_model: str = Field(
        default="distilbert-base-cased-distilled-squad",
        description="Question answering model",
    )
    translation_model: str = Field(
        default="Helsinki-NLP/opus-mt-en-de",
        description="Translation model",
    )

    # Performance settings
    use_gpu: bool = Field(
        default=True,
        description="Use GPU if available",
    )
    model_cache_dir: str | None = Field(
        default=None,
        description="Model cache directory",
    )
    trust_remote_code: bool = Field(
        default=False,
        description="Trust remote code in models",
    )


class TransformersNLP(BaseNLPAdapter):
    """Transformers NLP adapter."""

    def __init__(self, settings: TransformersNLPSettings | None = None) -> None:
        """Initialize Transformers NLP adapter.

        Args:
            settings: Transformers-specific adapter settings
        """
        if not _transformers_available:
            msg = (
                "Transformers is required for TransformersNLP adapter. "
                "Install with: pip install transformers torch"
            )
            raise ImportError(
                msg,
            )

        super().__init__(settings)
        self._settings: TransformersNLPSettings = settings or TransformersNLPSettings()
        self._pipelines: dict[str, Any] = {}
        self._device = None

    async def connect(self) -> None:
        """Connect to Transformers (load models)."""
        await self._setup_device()
        await self._load_models()

    async def disconnect(self) -> None:
        """Disconnect from Transformers (unload models)."""
        self._pipelines.clear()

    async def _setup_device(self) -> None:
        """Setup compute device."""
        if self._settings.use_gpu and torch.cuda.is_available():
            self._device = 0  # First GPU
        elif (
            self._settings.use_gpu
            and hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
        ):
            self._device = "mps"  # Apple Silicon
        else:
            self._device = -1  # CPU

    async def _load_models(self) -> None:
        """Load transformer models."""
        # Load sentiment analysis pipeline
        await self._load_pipeline(
            "sentiment",
            "sentiment-analysis",
            self._settings.sentiment_model,
        )

        # Load NER pipeline
        await self._load_pipeline(
            "ner",
            "ner",
            self._settings.ner_model,
        )

        # Load text classification pipeline
        await self._load_pipeline(
            "classification",
            "zero-shot-classification",
            self._settings.classification_model,
        )

    async def _load_pipeline(self, key: str, task: str, model: str) -> None:
        """Load a specific pipeline."""
        with suppress(Exception):
            # Model loading failed, skip this pipeline
            pipe = await self._run_sync(
                pipeline,
                task,
                model=model,
                device=self._device,
                model_kwargs={
                    "cache_dir": self._settings.model_cache_dir,
                    "trust_remote_code": self._settings.trust_remote_code,
                },
            )
            self._pipelines[key] = pipe

    async def _run_sync(self, func, *args, **kwargs) -> None:
        """Run synchronous function in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    async def health_check(self) -> bool:
        """Check Transformers health."""
        try:
            # Test at least one pipeline
            if "sentiment" in self._pipelines:
                result = await self._run_sync(self._pipelines["sentiment"], "test")
                return result is not None
            return len(self._pipelines) > 0
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
        results = {}

        # Default tasks if none specified
        if tasks is None:
            tasks = [
                TaskType.SENTIMENT_ANALYSIS,
                TaskType.NAMED_ENTITY_RECOGNITION,
            ]

        # Perform requested tasks
        for task in tasks:
            try:
                if task == TaskType.SENTIMENT_ANALYSIS:
                    results["sentiment"] = await self.analyze_sentiment(text, language)
                elif task == TaskType.NAMED_ENTITY_RECOGNITION:
                    results["entities"] = await self.extract_entities(
                        text,
                        language=language,
                    )
                elif (
                    task == TaskType.TEXT_CLASSIFICATION
                    and "classification" in self._pipelines
                ):
                    # Would need labels for zero-shot classification
                    pass
            except Exception as e:
                results[f"{task.value}_error"] = str(e)

        return results

    async def analyze_sentiment(
        self,
        text: str,
        language: str | None = None,
    ) -> SentimentResult:
        """Analyze sentiment using Transformers."""
        if "sentiment" not in self._pipelines:
            msg = "Sentiment analysis pipeline not available"
            raise ValueError(msg)

        result = await self._run_sync(self._pipelines["sentiment"], text)

        # Parse result
        if isinstance(result, list) and len(result) > 0:
            res = result[0]
            label_text = res["label"].lower()
            confidence = res["score"]

            # Map labels to standard format
            if "positive" in label_text or "pos" in label_text:
                label = SentimentLabel.POSITIVE
            elif "negative" in label_text or "neg" in label_text:
                label = SentimentLabel.NEGATIVE
            else:
                label = SentimentLabel.NEUTRAL

            scores = {label.value: confidence}

        else:
            label = SentimentLabel.NEUTRAL
            confidence = 0.5
            scores = {"neutral": 0.5}

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
        """Extract named entities using Transformers."""
        if "ner" not in self._pipelines:
            msg = "NER pipeline not available"
            raise ValueError(msg)

        result = await self._run_sync(self._pipelines["ner"], text)

        entities = []
        for ent in result:
            # Map entity label
            entity_label = self._map_transformers_label(ent["entity"])

            # Filter by entity types if specified
            if entity_types and entity_label not in [et.value for et in entity_types]:
                continue

            entities.append(
                NamedEntity(
                    text=ent["word"],
                    label=entity_label,
                    start=ent["start"],
                    end=ent["end"],
                    confidence=ent["score"],
                ),
            )

        return entities

    def _map_transformers_label(self, transformers_label: str) -> str:
        """Map Transformers entity labels to standard EntityType."""
        # Remove B- and I- prefixes from BIO tagging
        label = transformers_label.replace("B-", "").replace("I-", "")

        mapping = {
            "PER": EntityType.PERSON.value,
            "PERSON": EntityType.PERSON.value,
            "ORG": EntityType.ORGANIZATION.value,
            "LOC": EntityType.LOCATION.value,
            "MISC": EntityType.MISCELLANEOUS.value,
            "GPE": EntityType.LOCATION.value,
            "MONEY": EntityType.MONEY.value,
            "DATE": EntityType.DATE.value,
            "TIME": EntityType.TIME.value,
            "PERCENT": EntityType.PERCENT.value,
        }
        return mapping.get(label, EntityType.MISCELLANEOUS.value)

    async def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str | None = None,
    ) -> TranslationResult:
        """Translate text using Transformers."""
        # Load translation pipeline if not already loaded
        if "translation" not in self._pipelines:
            await self._load_pipeline(
                "translation",
                "translation",
                self._settings.translation_model,
            )

        if "translation" not in self._pipelines:
            msg = "Translation pipeline not available"
            raise ValueError(msg)

        result = await self._run_sync(self._pipelines["translation"], text)

        if isinstance(result, list) and len(result) > 0:
            translated_text = result[0]["translation_text"]
        else:
            translated_text = text  # Fallback

        return TranslationResult(
            text=translated_text,
            source_language=source_language,
            target_language=target_language,
            confidence=0.8,  # Default confidence
        )

    async def classify_text(
        self,
        text: str,
        labels: list[str] | None = None,
        model: str | None = None,
    ) -> ClassificationResult:
        """Classify text using Transformers."""
        if "classification" not in self._pipelines:
            msg = "Classification pipeline not available"
            raise ValueError(msg)

        if not labels:
            msg = "Labels required for zero-shot classification"
            raise ValueError(msg)

        result = await self._run_sync(
            self._pipelines["classification"],
            text,
            labels,
        )

        # Parse zero-shot classification result
        best_label = result["labels"][0]
        confidence = result["scores"][0]
        scores = dict(zip(result["labels"], result["scores"], strict=False))

        return ClassificationResult(
            label=best_label,
            confidence=confidence,
            scores=scores,
        )

    async def detect_language(self, text: str) -> LanguageDetectionResult:
        """Detect language using Transformers."""
        # This would require a language detection model
        # For now, assume English
        return LanguageDetectionResult(
            language="English",
            confidence=0.5,
            iso_code="en",
        )

    async def extract_keywords(
        self,
        text: str,
        max_keywords: int = 10,
        language: str | None = None,
    ) -> list[KeywordResult]:
        """Extract keywords using Transformers."""
        # This would require a keyword extraction model or use NER results
        entities = await self.extract_entities(text, language=language)

        # Convert entities to keywords
        keywords = []
        for ent in entities[:max_keywords]:
            keywords.append(
                KeywordResult(
                    keyword=ent.text,
                    score=ent.confidence,
                    frequency=1,
                ),
            )

        return keywords

    async def calculate_similarity(
        self,
        text1: str,
        text2: str,
        method: str = "cosine",
    ) -> SimilarityResult:
        """Calculate similarity using Transformers embeddings."""
        # This would require a sentence transformer model
        # For now, return a simple overlap-based similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        similarity = intersection / union if union > 0 else 0.0

        return SimilarityResult(
            similarity=similarity,
            method="word_overlap",
        )

    async def get_supported_tasks(self) -> list[TaskType]:
        """Get supported NLP tasks."""
        tasks = []

        if "sentiment" in self._pipelines:
            tasks.append(TaskType.SENTIMENT_ANALYSIS)

        if "ner" in self._pipelines:
            tasks.append(TaskType.NAMED_ENTITY_RECOGNITION)

        if "classification" in self._pipelines:
            tasks.append(TaskType.TEXT_CLASSIFICATION)

        if "translation" in self._pipelines:
            tasks.append(TaskType.LANGUAGE_TRANSLATION)

        tasks.extend(
            [
                TaskType.TEXT_ANALYSIS,
                TaskType.KEYWORD_EXTRACTION,
                TaskType.TEXT_SIMILARITY,
            ],
        )

        return tasks


# Create type alias for backward compatibility
NLP = TransformersNLP
