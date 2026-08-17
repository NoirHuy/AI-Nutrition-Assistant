from typing import List, Optional, Dict, Any
import logging
import os
import time

from pathlib import Path

import edc.utils.llm_utils as llm_utils

logger = logging.getLogger(__name__)


class Extractor:
    """First stage: Open Information Extraction.

    v2 changes (Week 2):
    - LLM/parser errors are no longer silent. Each call now tracks
      ``triples_input`` (count of bracketed strings seen by the parser),
      ``triples_parsed`` (kept after parsing), ``triples_failed`` (dropped),
      and the raw LLM completion (truncated) for debugging.
    - Optional ``max_retries`` controls the retry policy on API failure.
    """

    def __init__(
        self,
        model=None,
        tokenizer=None,
        openai_model: Optional[str] = None,
        max_retries: int = 1,
    ) -> None:
        assert openai_model is not None or (model is not None and tokenizer is not None)
        self.model = model
        self.tokenizer = tokenizer
        self.openai_model = openai_model
        self.max_retries = max(0, int(max_retries))

        # Optional metrics aggregation across calls
        self.metrics: Dict[str, int] = {
            "calls": 0,
            "api_failures": 0,
            "triples_input": 0,
            "triples_parsed": 0,
            "triples_failed": 0,
        }

    # ------------------------------------------------------------------

    def extract(
        self,
        input_text_str: str,
        few_shot_examples_str: str,
        prompt_template_str: str,
        entities_hint: Optional[str] = None,
        relations_hint: Optional[str] = None,
    ) -> List[List[str]]:
        """Extract triples from ``input_text_str`` using the LLM.

        Returns a list of ``[subject, relation, object]`` triples, or an
        empty list if the LLM call fails completely.
        """
        self.metrics["calls"] += 1

        filled_prompt = prompt_template_str.format_map(
            {
                "few_shot_examples": few_shot_examples_str,
                "input_text": input_text_str,
                "entities_hint": entities_hint or "",
                "relations_hint": relations_hint or "",
            }
        )
        messages = [{"role": "user", "content": filled_prompt}]

        completion = self._call_llm_with_retry(messages)
        if completion is None:
            self.metrics["api_failures"] += 1
            logger.error("[EXTRACT] LLM call failed after %d retries", self.max_retries)
            return []

        triples_pre_parse = completion.count("[")
        self.metrics["triples_input"] += triples_pre_parse

        extracted = llm_utils.parse_raw_triplets(completion, log_failures=True)

        # Diff between bracketed segments and parsed triples gives us
        # the failure count for this batch.
        failures_this_call = max(0, triples_pre_parse - len(extracted))
        self.metrics["triples_parsed"] += len(extracted)
        self.metrics["triples_failed"] += failures_this_call

        return extracted

    # ------------------------------------------------------------------

    def _call_llm_with_retry(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """Call the LLM, retrying on network/timeout errors."""
        attempts = self.max_retries + 1  # initial + retries
        last_exc = None
        for attempt in range(attempts):
            try:
                if self.openai_model is None:
                    completion = llm_utils.generate_completion_transformers(
                        messages, self.model, self.tokenizer, answer_prepend="Triplets: "
                    )
                else:
                    completion = llm_utils.api_chat_completion(
                        self.openai_model, None, messages, max_tokens=1024
                    )
                if not completion:
                    raise RuntimeError("LLM returned empty completion")
                return completion
            except Exception as exc:  # pragma: no cover - network errors
                last_exc = exc
                logger.warning(
                    "[EXTRACT] LLM call failed on attempt %d/%d: %s",
                    attempt + 1, attempts, exc,
                )
                if attempt + 1 < attempts:
                    time.sleep(2 ** attempt)  # exponential backoff

        logger.error("[EXTRACT] LLM call exhausted all retries: %s", last_exc)
        return None

    # ------------------------------------------------------------------

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of the running metrics for the caller."""
        return dict(self.metrics)

    def reset_metrics(self) -> None:
        for k in self.metrics:
            self.metrics[k] = 0
