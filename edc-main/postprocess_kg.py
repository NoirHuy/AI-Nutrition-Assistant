"""
postprocess_kg.py
=================
Bước hậu xử lý sau khi EDC chạy xong: Khử trùng lặp thực thể.

Vấn đề: Sau khi EDC trích xuất từ nhiều chunks khác nhau, cùng một thực thể
có thể xuất hiện với nhiều tên khác nhau:
  - "tiểu_đường" vs "bệnh_tiểu_đường" vs "tiểu_đường_tuýp_2"
  - "chất_xơ" vs "chất_xơ_ăn_kiêng" vs "dietary_fiber"

Script này:
  1. Đọc file canon_kg.txt từ output của EDC
  2. Dùng Jina Embeddings để tính cosine similarity giữa các tên thực thể
  3. Gộp các thực thể tương đồng (similarity > threshold) về dạng chuẩn
  4. Ghi ra file kg_deduplicated.txt

Cách dùng:
  python postprocess_kg.py \
      --kg_file "./output/diabetes_kg_vi/iter0/canon_kg.txt" \
      --output_file "./output/diabetes_kg_vi/iter0/kg_deduplicated.txt" \
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
    """Gọi Jina API để lấy embeddings cho danh sách văn bản."""
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
# Đọc file KG
# ─────────────────────────────────────────────────────────────

def load_kg(kg_file: str) -> list[list[str]]:
    """Đọc file canon_kg.txt — mỗi dòng là list các [S, R, O] triples."""
    triples = []
    with open(kg_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = ast.literal_eval(line)
                # Mỗi dòng có thể là list các triples
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, list) and len(item) == 3:
                            triples.append([str(x) for x in item])
            except Exception as e:
                logger.debug(f"Bỏ qua dòng không parse được: {line} — {e}")
    return triples


# ─────────────────────────────────────────────────────────────
# Entity Deduplication
# ─────────────────────────────────────────────────────────────

def normalize_entity(entity: str) -> str:
    """Chuẩn hóa tên thực thể: lowercase, thay _ bằng space để embed."""
    return entity.lower().replace("_", " ").strip()


def build_entity_clusters(
    entities: list[str],
    embeddings: np.ndarray,
    threshold: float = 0.90,
) -> dict[str, str]:
    """
    Gộp các thực thể tương đồng.
    Trả về dict: entity_gốc → entity_đại_diện (canonical).
    Dùng greedy clustering: thực thể đầu tiên trong cluster là canonical.
    """
    n = len(entities)
    canonical_map = {}  # entity → canonical_entity
    clusters = []  # list of (canonical, set of members)

    for i in range(n):
        assigned = False
        for canonical, members in clusters:
            # So sánh với canonical của cluster
            canonical_idx = entities.index(canonical)
            sim = cosine_similarity(embeddings[i], embeddings[canonical_idx])
            if sim >= threshold:
                members.add(entities[i])
                canonical_map[entities[i]] = canonical
                assigned = True
                break
        if not assigned:
            # Tạo cluster mới
            clusters.append((entities[i], {entities[i]}))
            canonical_map[entities[i]] = entities[i]

    logger.info(f"  {n} thực thể → {len(clusters)} cluster sau dedup (threshold={threshold})")
    return canonical_map


def deduplicate_kg(
    triples: list[list[str]],
    similarity_threshold: float,
    jina_key: str,
) -> list[list[str]]:
    """Pipeline khử trùng lặp thực thể."""

    # Thu thập tất cả thực thể (subject + object)
    all_entities_raw = set()
    for s, r, o in triples:
        all_entities_raw.add(s)
        all_entities_raw.add(o)

    all_entities = list(all_entities_raw)
    logger.info(f"Tổng số thực thể duy nhất (raw): {len(all_entities)}")

    if len(all_entities) == 0:
        return triples

    # Chuẩn hóa để embed
    normalized = [normalize_entity(e) for e in all_entities]

    logger.info("Đang lấy Jina embeddings cho các thực thể...")
    # Gửi theo batch 50 để tránh quá tải API
    batch_size = 50
    all_embeddings = []
    for i in range(0, len(normalized), batch_size):
        batch = normalized[i : i + batch_size]
        embs = get_jina_embeddings(batch, jina_key)
        all_embeddings.append(embs)
    embeddings = np.vstack(all_embeddings)

    # Clustering
    logger.info("Clustering thực thể tương đồng...")
    canonical_map = build_entity_clusters(all_entities, embeddings, threshold=similarity_threshold)

    # Áp dụng canonical_map vào triples
    deduped_triples = []
    seen = set()
    for s, r, o in triples:
        s_canon = canonical_map.get(s, s)
        o_canon = canonical_map.get(o, o)
        triple_key = (s_canon, r, o_canon)
        if triple_key not in seen:
            deduped_triples.append([s_canon, r, o_canon])
            seen.add(triple_key)

    logger.info(f"Triples trước dedup: {len(triples)} → sau dedup: {len(deduped_triples)}")
    return deduped_triples


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Khử trùng lặp thực thể trong KG sau EDC")
    parser.add_argument("--kg_file", required=True, help="File canon_kg.txt từ output EDC")
    parser.add_argument("--output_file", required=True, help="File output sau deduplication")
    parser.add_argument("--similarity_threshold", type=float, default=0.90,
                        help="Ngưỡng cosine similarity để gộp thực thể (mặc định: 0.90)")
    args = parser.parse_args()

    jina_key = os.environ.get("JINA_KEY", "")
    if not jina_key:
        logger.error("JINA_KEY không được đặt. Vui lòng set biến môi trường JINA_KEY.")
        return

    # Đọc KG
    logger.info(f"Đọc file KG: {args.kg_file}")
    triples = load_kg(args.kg_file)
    logger.info(f"Tổng số triples: {len(triples)}")

    if not triples:
        logger.warning("Không tìm thấy triple nào. Kiểm tra lại file input.")
        return

    # Khử trùng lặp
    deduped = deduplicate_kg(triples, args.similarity_threshold, jina_key)

    # Ghi output
    os.makedirs(os.path.dirname(args.output_file) if os.path.dirname(args.output_file) else ".", exist_ok=True)
    with open(args.output_file, "w", encoding="utf-8") as f:
        for triple in deduped:
            f.write(str(triple) + "\n")

    logger.info(f"✅ Đã ghi {len(deduped)} triples vào: {args.output_file}")

    # In thống kê
    subjects = set(t[0] for t in deduped)
    objects = set(t[2] for t in deduped)
    relations = set(t[1] for t in deduped)
    print(f"\n📊 Thống kê KG sau deduplication:")
    print(f"   Triples: {len(deduped)}")
    print(f"   Subjects: {len(subjects)}")
    print(f"   Relations: {len(relations)}")
    print(f"   Objects: {len(objects)}")
    print(f"   Relations xuất hiện: {sorted(relations)}")


if __name__ == "__main__":
    main()
