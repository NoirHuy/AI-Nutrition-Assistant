"""
translate_kg_to_neo4j.py
========================
Dịch file kg_deduplicated.txt từ tiếng Anh sang tiếng Việt,
giữ nguyên cấu trúc ['subject', 'relation', 'object'],
rồi đẩy lên Neo4j.

Cách dùng:
  python translate_kg_to_neo4j.py `
      --kg_file "./output/diabetes_en_kg/iter0/kg_deduplicated.txt" `
      --output_file "./output/diabetes_en_kg/iter0/kg_vi.txt" `
      --uri "bolt://localhost:7687" `
      --user "neo4j" `
      --password "mypassword123" `
      --label "TieuDuongKG"
"""

import ast
import re
import os
import json
import time
import argparse
import logging
import openai
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Load / Save
# ─────────────────────────────────────────────────────────────

def load_triples(kg_file: str) -> list[list[str]]:
    triples = []
    with open(kg_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = ast.literal_eval(line)
                if isinstance(parsed, list) and len(parsed) == 3:
                    triples.append([str(x) for x in parsed])
            except Exception as e:
                logger.debug(f"Skipping: {line} — {e}")
    return triples


def save_triples(triples: list[list[str]], output_file: str):
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for t in triples:
            f.write(str(t) + "\n")
    logger.info(f"✅ Đã lưu {len(triples)} triples vào: {output_file}")


# ─────────────────────────────────────────────────────────────
# Translation via Groq
# ─────────────────────────────────────────────────────────────

BATCH_SIZE = 20  # số triple mỗi lần gửi

def build_translation_prompt(triples_batch: list[list[str]]) -> str:
    triples_str = json.dumps(triples_batch, ensure_ascii=False, indent=2)
    return f"""Bạn là chuyên gia y tế và dinh dưỡng, thành thạo dịch thuật Anh-Việt.

Dưới đây là danh sách các triple từ một Knowledge Graph về dinh dưỡng và tiểu đường.
Mỗi triple có dạng [subject, relation, object].

NHIỆM VỤ:
1. Dịch subject và object sang tiếng Việt y tế chuẩn (dùng thuật ngữ phổ biến, dễ hiểu).
2. Dịch relation sang tiếng Việt theo bảng ánh xạ sau (PHẢI dùng đúng các cụm này):
   - "treats"               → "hỗ trợ điều trị"
   - "prevents"             → "phòng ngừa"
   - "aggravates"           → "làm trầm trọng"
   - "recommended for"      → "được khuyến nghị cho"
   - "contraindicated for"  → "chống chỉ định với"
   - "deficiency causes"    → "thiếu hụt gây ra"
   - "enhances absorption"  → "tăng cường hấp thu"
   - "restricts"            → "cần hạn chế ở"
   - "requires"             → "cần bổ sung ở"
   - "contains"             → "cung cấp"
   - "reduces"              → "làm giảm"
   - "increases"            → "làm tăng"
   - "associated with"      → "là yếu tố nguy cơ của"
   - "daily intake"         → "lượng khuyến nghị"
   - "food source"          → "cung cấp"
   - "symptom of"           → "là triệu chứng của"
3. Giữ nguyên cấu trúc JSON list of lists.
4. Thay dấu cách trong tên thực thể bằng dấu gạch dưới (_).

INPUT:
{triples_str}

OUTPUT (chỉ trả về JSON, không giải thích):"""


def translate_triples_with_llm(
    triples: list[list[str]],
    groq_key: str,
    model: str = "llama-3.3-70b-versatile",
    delay: float = 1.0,
) -> list[list[str]]:
    client = openai.OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=groq_key,
    )

    translated = []
    total_batches = (len(triples) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(triples), BATCH_SIZE):
        batch = triples[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info(f"  Dịch batch {batch_num}/{total_batches} ({len(batch)} triples)...")

        prompt = build_translation_prompt(batch)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1024,
            )
            raw = response.choices[0].message.content.strip()

            # Parse JSON
            # Tìm phần JSON trong response
            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, list):
                    translated.extend(parsed)
                    logger.info(f"    ✓ Dịch được {len(parsed)} triples")
                else:
                    logger.warning(f"    ⚠ Kết quả không phải list, giữ nguyên batch.")
                    translated.extend(batch)
            else:
                logger.warning(f"    ⚠ Không tìm thấy JSON, giữ nguyên batch.")
                translated.extend(batch)

        except Exception as e:
            logger.warning(f"    LLM error: {e}. Giữ nguyên batch.")
            translated.extend(batch)

        time.sleep(delay)

    return translated


# ─────────────────────────────────────────────────────────────
# Neo4j Import
# ─────────────────────────────────────────────────────────────

def relation_to_cypher_type(relation: str) -> str:
    cleaned = re.sub(r"[^a-zA-ZÀ-ỹ0-9\s_]", "", relation)
    return cleaned.strip().upper().replace(" ", "_")


def import_to_neo4j(triples: list[list[str]], driver, database: str, label: str):
    with driver.session(database=database) as session:
        try:
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_name IF NOT EXISTS "
                f"FOR (n:`{label}`) REQUIRE n.name IS UNIQUE"
            )
        except Exception:
            pass

        success = 0
        failed = 0
        for triple in triples:
            if len(triple) != 3:
                continue
            s, r, o = str(triple[0]), str(triple[1]), str(triple[2])
            rel_type = relation_to_cypher_type(r)
            query = (
                f"MERGE (a:`{label}` {{name: $subject}}) "
                f"MERGE (b:`{label}` {{name: $object}}) "
                f"MERGE (a)-[:`{rel_type}` {{relation: $relation}}]->(b)"
            )
            try:
                session.run(query, subject=s, object=o, relation=r)
                success += 1
            except Exception as e:
                logger.warning(f"Failed: ({s}, {r}, {o}) — {e}")
                failed += 1

        logger.info(f"✅ Neo4j: Imported {success} | Failed {failed}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dịch KG sang tiếng Việt và đẩy lên Neo4j")
    parser.add_argument("--kg_file", required=True, help="File kg_deduplicated.txt đầu vào")
    parser.add_argument("--output_file", required=True, help="File .txt tiếng Việt đầu ra")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--label", default="TieuDuongKG",
                        help="Label Neo4j cho KG này (default: TieuDuongKG)")
    parser.add_argument("--skip_import", action="store_true",
                        help="Chỉ dịch, không đẩy lên Neo4j")
    args = parser.parse_args()

    groq_key = os.environ.get("GROQ_KEY", "")
    if not groq_key:
        logger.error("GROQ_KEY chưa được đặt.")
        return

    # Load
    logger.info(f"Đọc file: {args.kg_file}")
    triples = load_triples(args.kg_file)
    logger.info(f"Tổng số triples: {len(triples)}")

    # Translate
    logger.info("Dịch sang tiếng Việt qua Groq LLM...")
    vi_triples = translate_triples_with_llm(triples, groq_key)

    # Save
    save_triples(vi_triples, args.output_file)

    # Print sample
    print("\n📋 Mẫu 5 triple đầu:")
    for t in vi_triples[:5]:
        print(f"   {t}")

    if args.skip_import:
        logger.info("Bỏ qua bước import Neo4j (--skip_import).")
        return

    # Import Neo4j
    logger.info(f"Kết nối Neo4j: {args.uri} / database={args.database} / label={args.label}")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        driver.verify_connectivity()
        logger.info("Kết nối thành công.")
        import_to_neo4j(vi_triples, driver, args.database, args.label)
    finally:
        driver.close()

    print(f"\n🔍 Cypher để xem KG tiếng Việt:")
    print(f"   MATCH (n:`{args.label}`)-[r]->(m:`{args.label}`) RETURN n, r, m LIMIT 50")


if __name__ == "__main__":
    main()
