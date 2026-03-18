"""
preprocess_document_en.py
=========================
Preprocessing pipeline for English documents — EDC Framework.

Steps:
  1. Clean        : Remove journal headers, footers, citations, page numbers.
  2. Chunking     : Split document into fixed-size sentence chunks.
  3. Coreference  : Resolve pronouns / ambiguous references via Groq LLM (optional).
  4. Output       : Write .txt file for EDC (one chunk per line).

Usage:
  python preprocess_document_en.py \\
      --input_file "./datasets/Dietary and Nutritional Guidelines for People with Diabetes.txt" \\
      --output_file "./datasets/diabetes_en.txt" \\
      --sentences_per_chunk 3 \\
      --context_window 1
"""

import os
import re
import argparse
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# STEP 0: Clean raw text
# ─────────────────────────────────────────────────────────────

def clean_raw_text(raw_text: str) -> str:
    """
    Remove journal headers, author names, page numbers, citation lines,
    and merge all content into a single continuous text block.
    """
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    skip_patterns = [
        r'^Nutrients \d{4},',           # journal header e.g. "Nutrients 2023, 15, 4314"
        r'https?://\S+',                # DOI / URL lines
        r'^\d+ of \d+$',               # page indicator "2 of 4"
        r'^\[\d',                       # reference lines [1], [2]...
        r'^Katsumi',                    # author name
        r'^doi:',                       # DOI lines
    ]

    content_lines = []
    for line in lines:
        if any(re.search(pat, line) for pat in skip_patterns):
            continue
        content_lines.append(line)

    return " ".join(content_lines)


# ─────────────────────────────────────────────────────────────
# STEP 1: Sentence splitting & chunking
# ─────────────────────────────────────────────────────────────

def split_into_sentences(text: str) -> list[str]:
    """
    Split English text into sentences.
    Handles common edge cases:
      - Decimal numbers (e.g. 0.8 g/kg)
      - Common abbreviations (e.g., i.e., e.g., vs., Dr., Mr.)
    """
    # Protect decimal numbers: 0.8 → 0<DOT>8
    text = re.sub(r'(\d)\.(\d)', r'\1<DOT>\2', text)

    # Protect common abbreviations
    abbrevs = r'\b(e\.g|i\.e|vs|Dr|Mr|Mrs|Prof|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    text = re.sub(abbrevs + r'\.\s', r'\1<DOT> ', text)

    # Split on sentence-ending punctuation
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    sentences = [
        s.replace('<DOT>', '.').strip()
        for s in raw_sentences
        if s.strip() and len(s.strip()) > 10
    ]
    return sentences


def chunk_sentences(sentences: list[str], chunk_size: int = 3) -> list[str]:
    """Group sentences into fixed-size chunks."""
    chunks = []
    for i in range(0, len(sentences), chunk_size):
        chunk = " ".join(sentences[i : i + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


# ─────────────────────────────────────────────────────────────
# STEP 2: Coreference Resolution — Groq LLM
# ─────────────────────────────────────────────────────────────

def build_coreference_prompt(context_chunk: str, current_chunk: str) -> str:
    """
    Build a prompt asking the LLM to replace pronouns and ambiguous
    references with explicit entity names, using the previous chunk as context.
    """
    if context_chunk:
        return f"""You are a coreference resolution tool for English medical text.

PREVIOUS CONTEXT (for reference):
{context_chunk}

CURRENT CHUNK TO PROCESS:
{current_chunk}

TASK:
- Read the CURRENT CHUNK and replace all pronouns and ambiguous references \
(e.g., "it", "this", "they", "these guidelines", "this approach", "such diets") \
with specific entity names drawn from the context.
- If the chunk is already unambiguous, do not change anything.
- Return ONLY the processed chunk. NO explanations, NO headers.

Processed chunk:"""
    else:
        return f"""You are a coreference resolution tool for English medical text.

CURRENT CHUNK TO PROCESS:
{current_chunk}

TASK:
- Replace any pronouns or ambiguous references with specific entity names \
if they can be inferred from the chunk itself.
- If already unambiguous, do not change anything.
- Return ONLY the processed chunk. NO explanations.

Processed chunk:"""


def resolve_coreference_with_llm(
    chunks: list[str],
    groq_api_key: str,
    model: str = "llama-3.3-70b-versatile",
    context_window: int = 1,
    delay: float = 0.5,
) -> list[str]:
    """
    Resolve coreferences for all chunks via Groq LLM with a sliding context window.
    Each chunk is resolved using the previous `context_window` resolved chunks as context.
    """
    import openai

    client = openai.OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=groq_api_key,
    )

    resolved_chunks = []

    for i, chunk in enumerate(chunks):
        logger.info(f"  Resolving coreference: chunk {i+1}/{len(chunks)}")

        context_start = max(0, i - context_window)
        context = " ".join(resolved_chunks[context_start:i]) if resolved_chunks else ""

        prompt = build_coreference_prompt(context, chunk)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=512,
            )
            resolved = response.choices[0].message.content.strip()
            # Strip any LLM-added prefix
            for prefix in ["Processed chunk:", "Result:"]:
                if resolved.startswith(prefix):
                    resolved = resolved[len(prefix):].strip()
            resolved_chunks.append(resolved)
        except Exception as e:
            logger.warning(f"    LLM error on chunk {i+1}: {e}. Keeping original.")
            resolved_chunks.append(chunk)

        time.sleep(delay)

    return resolved_chunks


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def preprocess(
    input_file: str,
    output_file: str,
    sentences_per_chunk: int = 3,
    context_window: int = 1,
    skip_coreference: bool = False,
):
    groq_key = os.environ.get("GROQ_KEY", "")

    # ── Read ──
    logger.info(f"Reading file: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # ── Clean ──
    logger.info("Cleaning raw text...")
    clean_text = clean_raw_text(raw_text)
    logger.info(f"  After cleaning: {len(clean_text)} characters")

    # ── Step 1: Chunking ──
    logger.info(f"Chunking ({sentences_per_chunk} sentences/chunk)...")
    sentences = split_into_sentences(clean_text)
    logger.info(f"  Total sentences: {len(sentences)}")
    chunks = chunk_sentences(sentences, chunk_size=sentences_per_chunk)
    logger.info(f"  Total chunks: {len(chunks)}")

    # ── Step 2: Coreference Resolution ──
    if skip_coreference:
        logger.info("Skipping coreference resolution (--skip_coreference).")
        processed_chunks = chunks
    elif not groq_key:
        logger.warning("GROQ_KEY not set. Skipping coreference resolution.")
        processed_chunks = chunks
    else:
        logger.info(f"Coreference resolution via Groq LLM (context_window={context_window})...")
        processed_chunks = resolve_coreference_with_llm(
            chunks,
            groq_api_key=groq_key,
            context_window=context_window,
        )

    # ── Write output ──
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        for chunk in processed_chunks:
            f.write(chunk.strip() + "\n")

    logger.info(f"✅ Written {len(processed_chunks)} chunks to: {output_file}")
    return processed_chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocess English documents for EDC Framework")
    parser.add_argument("--input_file", required=True, help="Path to input .txt file")
    parser.add_argument("--output_file", required=True, help="Path to output .txt file for EDC")
    parser.add_argument("--sentences_per_chunk", type=int, default=3,
                        help="Number of sentences per chunk (default: 3)")
    parser.add_argument("--context_window", type=int, default=1,
                        help="Number of previous chunks used as coref context (default: 1)")
    parser.add_argument("--skip_coreference", action="store_true",
                        help="Skip the coreference resolution step")
    args = parser.parse_args()

    preprocess(
        input_file=args.input_file,
        output_file=args.output_file,
        sentences_per_chunk=args.sentences_per_chunk,
        context_window=args.context_window,
        skip_coreference=args.skip_coreference,
    )
