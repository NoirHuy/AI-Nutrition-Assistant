"""
postprocess_kg_en.py
====================
Post-processing after EDC: entity deduplication for English KGs.

Problem: After EDC extracts triples from multiple chunks, the same entity
can appear under different surface forms:
  - "diabetes" vs "diabetes mellitus" vs "type 2 diabetes"
  - "dietary fiber" vs "fiber" vs "fibre"

This script:
  1. Reads canon_kg.txt from EDC output
  2. Uses Jina Embeddings to compute cosine similarity between entity names
  3. Merges similar entities (similarity > threshold) into a canonical form
  4. Writes deduplicated triples to kg_deduplicated.txt

Usage:
  python postprocess_kg_en.py \\
      --kg_file "./output/diabetes_en_kg/iter0/canon_kg.txt" \\
      --output_file "./output/diabetes_en_kg/iter0/kg_deduplicated.txt" \\
      --similarity_threshold 0.90
"""

import os
import ast
import re
import argparse
import logging
import numpy as np
import requests
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Jina Embeddings API
# ─────────────────────────────────────────────────────────────

def get_jina_embeddings(texts: list[str], jina_key: str, model: str = "jina-embeddings-v3") -> np.ndarray:
    """Call Jina API to get embeddings for a list of texts."""
    headers = {
        "Authorization": f"Bearer {jina_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "input": texts}
    response = requests.post("https://api.jina.ai/v1/embeddings", headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    return np.array([item["embedding"] for item in data["data"]])


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


# ─────────────────────────────────────────────────────────────
# Load KG
# ─────────────────────────────────────────────────────────────

def load_kg(kg_file: str) -> list[list[str]]:
    """Read canon_kg.txt — each line is a list of [S, R, O] triples."""
    triples = []
    with open(kg_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = ast.literal_eval(line)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, list) and len(item) == 3:
                            triples.append([str(x) for x in item])
            except Exception as e:
                logger.debug(f"Skipping unparseable line: {line} — {e}")
    return triples


# ─────────────────────────────────────────────────────────────
# Entity Deduplication
# ─────────────────────────────────────────────────────────────

def normalize_entity(entity: str) -> str:
    """Normalize entity name: lowercase, replace underscores with spaces."""
    return entity.lower().replace("_", " ").strip()


def build_entity_clusters(
    entities: list[str],
    embeddings: np.ndarray,
    threshold: float = 0.90,
) -> dict[str, str]:
    """
    Greedy clustering of similar entities.
    Returns dict: original_entity → canonical_entity.
    The first entity encountered in a cluster is the canonical representative.
    """
    n = len(entities)
    canonical_map = {}
    clusters = []  # list of (canonical, set of members)

    for i in range(n):
        assigned = False
        for canonical, members in clusters:
            canonical_idx = entities.index(canonical)
            sim = cosine_similarity(embeddings[i], embeddings[canonical_idx])
            if sim >= threshold:
                members.add(entities[i])
                canonical_map[entities[i]] = canonical
                assigned = True
                break
        if not assigned:
            clusters.append((entities[i], {entities[i]}))
            canonical_map[entities[i]] = entities[i]

    logger.info(f"  {n} entities → {len(clusters)} clusters after dedup (threshold={threshold})")
    return canonical_map


def deduplicate_kg(
    triples: list[list[str]],
    similarity_threshold: float,
    jina_key: str,
) -> list[list[str]]:
    """Full entity deduplication pipeline."""

    all_entities_raw = set()
    for s, r, o in triples:
        all_entities_raw.add(s)
        all_entities_raw.add(o)

    all_entities = list(all_entities_raw)
    logger.info(f"Total unique entities (raw): {len(all_entities)}")

    if len(all_entities) == 0:
        return triples

    normalized = [normalize_entity(e) for e in all_entities]

    logger.info("Fetching Jina embeddings for entities...")
    batch_size = 50
    all_embeddings = []
    for i in range(0, len(normalized), batch_size):
        batch = normalized[i : i + batch_size]
        embs = get_jina_embeddings(batch, jina_key)
        all_embeddings.append(embs)
    embeddings = np.vstack(all_embeddings)

    logger.info("Clustering similar entities...")
    canonical_map = build_entity_clusters(all_entities, embeddings, threshold=similarity_threshold)

    deduped_triples = []
    seen = set()
    for s, r, o in triples:
        s_canon = canonical_map.get(s, s)
        o_canon = canonical_map.get(o, o)
        triple_key = (s_canon, r, o_canon)
        if triple_key not in seen:
            deduped_triples.append([s_canon, r, o_canon])
            seen.add(triple_key)

    logger.info(f"Triples before dedup: {len(triples)} → after dedup: {len(deduped_triples)}")
    return deduped_triples


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Entity deduplication for English KG after EDC")
    parser.add_argument("--kg_file", required=True, help="canon_kg.txt from EDC output")
    parser.add_argument("--output_file", required=True, help="Output file after deduplication")
    parser.add_argument("--similarity_threshold", type=float, default=0.90,
                        help="Cosine similarity threshold for entity merging (default: 0.90)")
    args = parser.parse_args()

    jina_key = os.environ.get("JINA_KEY", "")
    if not jina_key:
        logger.error("JINA_KEY not set. Please set the JINA_KEY environment variable.")
        return

    # Load KG
    logger.info(f"Reading KG file: {args.kg_file}")
    triples = load_kg(args.kg_file)
    logger.info(f"Total triples: {len(triples)}")

    if not triples:
        logger.warning("No triples found. Check your input file.")
        return

    # Deduplicate
    deduped = deduplicate_kg(triples, args.similarity_threshold, jina_key)

    # Write output
    out_dir = os.path.dirname(args.output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output_file, "w", encoding="utf-8") as f:
        for triple in deduped:
            f.write(str(triple) + "\n")

    logger.info(f"✅ Written {len(deduped)} triples to: {args.output_file}")

    # Stats
    subjects  = set(t[0] for t in deduped)
    objects   = set(t[2] for t in deduped)
    relations = set(t[1] for t in deduped)
    print(f"\n📊 KG Stats after deduplication:")
    print(f"   Triples:   {len(deduped)}")
    print(f"   Subjects:  {len(subjects)}")
    print(f"   Relations: {len(relations)}")
    print(f"   Objects:   {len(objects)}")
    print(f"   Relations found: {sorted(relations)}")


if __name__ == "__main__":
    main()
