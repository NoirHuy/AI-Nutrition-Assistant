# -*- coding: utf-8 -*-
"""
sentence_rewriter.py v2 — Sentence splitter + coreference resolution.

v2 changes (Week 1):
- Splits the work in two steps:
  1. ``split_sentences`` does cheap, deterministic splitting via nltk
     (with a regex fallback if nltk is unavailable).
  2. ``resolve_coreferences`` calls the LLM ONLY to resolve pronouns
     against each already-split sentence (or batch of short sentences).
- Robust fallback: if the LLM call fails, the original split sentences
  are returned instead of an empty list, so downstream stages don't
  silently lose data.

Backward compatible: existing callers that use ``rewrite(chunk,
section_headers)`` continue to work, since the new pipeline runs
deterministic split first and LLM-coref on each sentence.
"""

import logging
import os
import re
from typing import List, Optional

from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)

# --- Sentences-splitting backend ---------------------------------------------

_NLTK_SENT_TOKENIZER = None


def _get_nltk_tokenizer():
    """Lazy-load nltk's PunktSentenceTokenizer.

    Returns ``None`` if nltk (or the 'punkt' resource) is not installed.
    The caller must then fall back to a regex-based splitter.
    """
    global _NLTK_SENT_TOKENIZER
    if _NLTK_SENT_TOKENIZER is not None:
        return _NLTK_SENT_TOKENIZER

    try:
        import nltk
        from nltk.tokenize import PunktTokenizer

        try:
            _NLTK_SENT_TOKENIZER = nltk.data.load("tokenizers/punkt/english.pickle")
        except Exception:
            try:
                nltk.download("punkt", quiet=True)
                nltk.download("punkt_tab", quiet=True)
                _NLTK_SENT_TOKENIZER = nltk.data.load("tokenizers/punkt/english.pickle")
            except Exception as exc:  # pragma: no cover - download failed
                logger.warning("nltk punkt resource unavailable: %s", exc)
                _NLTK_SENT_TOKENIZER = False  # signal: don't try again
                return None

        return _NLTK_SENT_TOKENIZER
    except ImportError:
        logger.warning("nltk is not installed; falling back to regex sentence split")
        _NLTK_SENT_TOKENIZER = False
        return None


_REGEX_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def split_sentences(text: str) -> List[str]:
    """Split ``text`` into sentences.

    Tries nltk first; falls back to a regex-based splitter (sentence-final
    punctuation followed by capital letter). Skips empty results.
    """
    if not text or not text.strip():
        return []

    tokenizer = _get_nltk_tokenizer()
    if tokenizer:
        raw = tokenizer.tokenize(text)
    else:
        raw = _REGEX_SPLIT_PATTERN.split(text.strip())

    sentences = []
    for s in raw:
        s = s.strip()
        if s and len(s) > 1:
            sentences.append(s)
    return sentences


# --- LLM coreference resolution ----------------------------------------------


class SentenceRewriter:
    """
    Splits text into smaller sentences using a deterministic backend (nltk /
    regex) and then performs coreference resolution using the LLM. Each
    output sentence is standalone and suitable for Information Extraction.
    """

    def __init__(
        self,
        model_name: str = "meta-llama/llama-3.3-70b-instruct",
        temperature: float = 0.0,
    ):
        logger.info("[SentenceRewriter] Initializing preprocessor LLM wrapper...")
        self.model_name = model_name
        self.temperature = temperature

        self.prompt = PromptTemplate(
            input_variables=["section_headers", "chunk_content"],
            template=(
                "You are an expert medical linguist and data engineer.\n"
                "I will give you a chunk of medical text from the section '{section_headers}'.\n"
                "Your task is to break this text down into simple, standalone, clinical English sentences.\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. Coreference Resolution: You MUST replace all pronouns (it, they, this, these, he, she, etc.) and implicit references (e.g., 'the disease', 'the drug', 'this treatment', 'the patients') with the explicit entity names they refer to, using the surrounding text or the section headers.\n"
                "2. Standalone: Every single sentence must make complete sense on its own without needing any preceding or succeeding context.\n"
                "3. Formatting: Output strictly ONE sentence per line. Do not use bullet points, numbering, or introductory/concluding conversational text. Just the sentences.\n\n"
                "Original Text:\n"
                "{chunk_content}\n\n"
                "Resolved Standalone Sentences (one per line):"
            ),
        )

        self.coref_prompt = PromptTemplate(
            input_variables=["section_headers", "sentence"],
            template=(
                "You are an expert medical linguist.\n"
                "Section context: {section_headers}.\n\n"
                "Rewrite the following sentence as a SINGLE standalone sentence by "
                "replacing every pronoun or implicit reference (it, they, this, these, "
                "the disease, the drug, the patients, etc.) with the explicit entity "
                "name from the section context. Preserve clinical accuracy.\n\n"
                "Sentence: {sentence}\n\n"
                "Resolved Sentence:"
            ),
        )

    # ------------------------------------------------------------------ public

    def split_sentences(self, chunk_content: str) -> List[str]:
        """Public wrapper to expose the deterministic split step."""
        return split_sentences(chunk_content)

    def resolve_coreferences(
        self, sentences: List[str], section_headers: str
    ) -> List[str]:
        """Resolve coreferences for each sentence via the LLM.

        On any per-sentence failure, the original sentence is kept so the
        downstream pipeline still receives something.
        """
        if not sentences:
            return []

        headers_value = section_headers or "Clinical Narrative Overview"
        resolved = []
        for sentence in sentences:
            try:
                fixed = self._resolve_single(sentence, headers_value)
                if fixed:
                    resolved.append(fixed)
                else:
                    resolved.append(sentence)
            except Exception as exc:  # pragma: no cover - network errors
                logger.warning(
                    "Coreference resolution failed for sentence (%s); keeping original. Error: %s",
                    sentence[:50],
                    exc,
                )
                resolved.append(sentence)
        return resolved

    def rewrite(self, chunk_content: str, section_headers: str) -> List[str]:
        """Backward-compatible entry point: split + resolve.

        Uses the deterministic splitter for the split phase and the LLM for
        the coreference phase. Falls back to the deterministic sentences if
        the LLM call fails entirely.
        """
        if not chunk_content or not chunk_content.strip():
            return []

        sentences = split_sentences(chunk_content)
        if not sentences:
            logger.warning("Sentence splitter produced no output; running LLM rewrite as last resort.")
            return self._legacy_rewrite(chunk_content, section_headers)

        resolved = self.resolve_coreferences(sentences, section_headers)
        if not resolved:
            return sentences
        return resolved

    # ---------------------------------------------------------------- private

    def _resolve_single(self, sentence: str, section_headers: str) -> Optional[str]:
        """Resolve a single sentence via the LLM."""
        import sys
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)

        import edc.utils.llm_utils as llm_utils

        user_message = self.coref_prompt.format(
            section_headers=section_headers,
            sentence=sentence,
        )
        messages = [{"role": "user", "content": user_message}]
        result = llm_utils.api_chat_completion(
            model=self.model_name,
            system_prompt=None,
            history=messages,
            temperature=self.temperature,
            max_tokens=512,
        )
        cleaned = result.strip()
        # Remove any leading list marker or markdown quote
        cleaned = re.sub(r"^[-*•\d+\.\s]+", "", cleaned)
        return cleaned or None

    def _legacy_rewrite(self, chunk_content: str, section_headers: str) -> List[str]:
        """Legacy combined-mode rewrite kept for callers that didn't split yet."""
        import sys
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)

        import edc.utils.llm_utils as llm_utils

        try:
            user_message = self.prompt.format(
                section_headers=section_headers,
                chunk_content=chunk_content,
            )
            messages = [{"role": "user", "content": user_message}]
            result = llm_utils.api_chat_completion(
                model=self.model_name,
                system_prompt=None,
                history=messages,
                temperature=self.temperature,
                max_tokens=2048,
            )
            lines = result.split("\n")
            sentences = []
            for line in lines:
                line = line.strip()
                if not line or line.lower().startswith("here are") or line.lower().startswith("resolved"):
                    continue
                line = line.lstrip("-*• ")
                line = re.sub(r"^\d+\.\s*", "", line)
                if line:
                    sentences.append(line)
            return sentences
        except Exception as e:
            logger.error(f"Error rewriting sentences: {e}")
            return []
