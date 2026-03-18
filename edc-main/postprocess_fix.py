"""
postprocess_fix.py
==================
Làm sạch kg_flat.txt cũ trước khi import vào Neo4j.

Các vấn đề được xử lý:
  1. Subject bị nhúng tiền tố số lượng: "100g_Đậu_Hà_lan" → "Đậu Hà lan"
  2. Object chứa giá trị số + đơn vị: "342.0_kcal_năng_lượng" → loại bỏ triple
  3. Chiều quan hệ bị đảo: [dưỡng_chất, 'giàu'/'chứa', thực_phẩm] → đảo lại
  4. Triple trùng lặp sau khi làm sạch → giữ 1 bản duy nhất

Usage:
  python postprocess_fix.py \\
      --input  ./output/food_vietnam_kg/kg_flat.txt \\
      --output ./output/food_vietnam_kg/kg_clean.txt
"""

import ast
import re
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Danh sách dưỡng chất phổ biến (để phát hiện
# triple bị đảo chiều)
# ─────────────────────────────────────────────
KNOWN_NUTRIENTS = {
    "protein", "chất béo", "carbohydrate", "chất xơ", "năng lượng",
    "canxi", "phospho", "sắt", "natri", "kali", "beta caroten",
    "vitamin b1", "vitamin b2", "vitamin c", "vitamin a", "vitamin d",
    "vitamin k", "cholesterol", "purin", "đường", "muối", "natri",
    "magie", "kẽm", "đồng", "selen", "iốt", "folate",
    # tiếng Anh
    "calcium", "iron", "fiber", "fat", "glucose", "sugar", "sodium",
    "potassium", "magnesium", "zinc", "phosphorus", "folate",
}

INVERTED_RELATIONS = {"giàu", "chứa", "nhiều", "ít", "rich_in", "contains"}


# ─────────────────────────────────────────────
# Rule 1: Chuẩn hóa tên thực thể
# ─────────────────────────────────────────────
def clean_entity_name(entity: str) -> str:
    """
    Xóa các tiền tố số lượng như '100g_', '2.5mg_', '342.0_kcal_'
    khỏi đầu tên thực thể. Sau đó chuẩn hóa dấu gạch dưới → khoảng trắng.
    """
    # Xóa tiền tố dạng: "100g_", "100_g_", "342.0_kcal_", "2.5mg_"
    entity = re.sub(r"^\d+[\.,]?\d*\s*[a-zA-Z]*g?\s*_?", "", entity)
    # Xóa hậu tố giá trị lẫn vào: "năng_lượng_346_kcal" → "năng lượng"
    entity = re.sub(r"_\d+[\.,]?\d*\s*[A-Za-z]+$", "", entity)
    # Thay _ → khoảng trắng, strip
    entity = entity.replace("_", " ").strip()
    return entity


# ─────────────────────────────────────────────
# Rule 2: Phát hiện Object là chuỗi giá trị số
# ─────────────────────────────────────────────
NUMERIC_VALUE_PATTERN = re.compile(
    r"^\d+[\.,]?\d*\s*(g|mg|kcal|mcg|ml|kg|µg|IU|mg/kg|g/kg|mmol).*",
    re.IGNORECASE
)

def is_numeric_value_object(obj: str) -> bool:
    """Trả về True nếu Object trông giống một chuỗi giá trị số + đơn vị."""
    return bool(NUMERIC_VALUE_PATTERN.match(obj.strip()))


# ─────────────────────────────────────────────
# Rule 3: Phát hiện và đảo chiều quan hệ sai
# ─────────────────────────────────────────────
def is_nutrient(name: str) -> bool:
    return name.lower().replace("_", " ").strip() in KNOWN_NUTRIENTS


def fix_inverted_relation(s: str, r: str, o: str):
    """
    Nếu Subject là dưỡng chất và Object trông giống thực phẩm
    với quan hệ 'giàu'/'chứa' → đảo ngược lại.
    Trả về (s, r, o) sau khi sửa (hoặc None nếu không sửa được).
    """
    if r.lower() in INVERTED_RELATIONS and is_nutrient(s) and not is_nutrient(o):
        logger.info(f"  [ĐẢO CHIỀU] ({s!r}, {r!r}, {o!r}) → ({o!r}, {r!r}, {s!r})")
        return o, r, s
    return s, r, o


# ─────────────────────────────────────────────
# Pipeline chính
# ─────────────────────────────────────────────
def process(input_path: str, output_path: str):
    # Đọc file
    raw_triples = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = ast.literal_eval(line)
                if isinstance(parsed, list) and len(parsed) == 3:
                    raw_triples.append([str(x) for x in parsed])
            except Exception as e:
                logger.debug(f"Bỏ qua dòng không parse được: {line!r} — {e}")

    logger.info(f"Đọc được {len(raw_triples)} triples từ {input_path}")

    stats = {"numeric_obj_removed": 0, "entity_cleaned": 0, "inverted_fixed": 0, "dedup_removed": 0}
    cleaned = []
    seen = set()

    for s, r, o in raw_triples:
        # Rule 2: Loại bỏ triple có Object là giá trị số
        if is_numeric_value_object(o):
            logger.debug(f"  [LOẠI BỎ - Object là số] ({s!r}, {r!r}, {o!r})")
            stats["numeric_obj_removed"] += 1
            continue

        # Rule 1: Làm sạch tên thực thể
        s_clean = clean_entity_name(s)
        o_clean = clean_entity_name(o)
        if s_clean != s or o_clean != o:
            stats["entity_cleaned"] += 1

        # Rule 2 lần 2: Sau khi clean, check lại Object (vì clean có thể lộ ra số)
        if is_numeric_value_object(o_clean):
            logger.debug(f"  [LOẠI BỎ - Object số sau clean] ({s_clean!r}, {r!r}, {o_clean!r})")
            stats["numeric_obj_removed"] += 1
            continue

        # Bỏ triple có Subject hoặc Object rỗng sau khi clean
        if not s_clean or not o_clean:
            stats["numeric_obj_removed"] += 1
            continue

        # Rule 3: Sửa chiều quan hệ bị đảo
        s_final, r_final, o_final = fix_inverted_relation(s_clean, r, o_clean)
        if (s_final, r_final, o_final) != (s_clean, r, o_clean):
            stats["inverted_fixed"] += 1

        # Rule 4: Loại bỏ trùng lặp
        key = (s_final.lower(), r_final.lower(), o_final.lower())
        if key in seen:
            stats["dedup_removed"] += 1
            continue
        seen.add(key)

        cleaned.append([s_final, r_final, o_final])

    # Ghi output
    with open(output_path, "w", encoding="utf-8") as f:
        for triple in cleaned:
            f.write(str(triple) + "\n")

    # Thống kê
    print("\n" + "="*55)
    print("📊 KẾT QUẢ LÀM SẠCH")
    print("="*55)
    print(f"   Input triples          : {len(raw_triples)}")
    print(f"   → Loại bỏ Object số   : {stats['numeric_obj_removed']}")
    print(f"   → Entity đã làm sạch  : {stats['entity_cleaned']}")
    print(f"   → Đảo chiều quan hệ   : {stats['inverted_fixed']}")
    print(f"   → Loại trùng lặp      : {stats['dedup_removed']}")
    print(f"   Output triples         : {len(cleaned)}")
    print(f"   Lưu tại               : {output_path}")
    print("="*55)

    subjects  = set(t[0] for t in cleaned)
    objects   = set(t[2] for t in cleaned)
    relations = set(t[1] for t in cleaned)
    print(f"\n🔗 Nodes (Subject)  : {len(subjects)}")
    print(f"🔗 Nodes (Object)   : {len(objects)}")
    print(f"🔗 Relations unique : {len(relations)}")
    print(f"   {sorted(relations)}")


def main():
    parser = argparse.ArgumentParser(description="Làm sạch kg_flat.txt trước khi import vào Neo4j")
    parser.add_argument("--input",  required=True, help="File kg_flat.txt cần làm sạch")
    parser.add_argument("--output", required=True, help="File kg_clean.txt đầu ra")
    args = parser.parse_args()
    process(args.input, args.output)


if __name__ == "__main__":
    main()
