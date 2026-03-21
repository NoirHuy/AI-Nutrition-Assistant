"""
import_nutrition_kg.py
======================
Import KG triples từ canon_kg.txt VÀ hàm lượng dinh dưỡng từ Excel vào Neo4j.

Mỗi thực phẩm (Food node) sẽ có:
  - Thuộc tính ngữ nghĩa: label Food, name
  - Thuộc tính số: calories, protein, fat, carbs, fiber, cholesterol,
                   calcium, phosphorus, iron, sodium, potassium,
                   beta_carotene, vitamin_a, vitamin_b1, vitamin_c
  - Quan hệ (edges): từ KG triple pipeline

Usage:
  python import_nutrition_kg.py \
      --kg_file   "./output/food_vietnam_kg/merged/canon_kg_merged.txt" \
      --excel     "../docs/food_vietnam_final.xlsx" \
      --password  "password"
"""

import ast
import re
import argparse
import logging
import pandas as pd
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# Known entity classification
# ─────────────────────────────────────────────────────────────

KNOWN_DISEASES = {
    "tiểu đường", "đái tháo đường", "tiểu đường tuýp 2",
    "cao huyết áp", "tăng huyết áp",
    "gút", "gout",
    "béo phì", "thừa cân",
    "suy thận", "suy thận mãn tính",
    "bệnh tim mạch", "tim mạch", "xơ vữa động mạch",
    "gan nhiễm mỡ", "viêm gan",
    "trào ngược dạ dày", "trào ngược dạ dày thực quản",
    "táo bón", "thiếu máu", "thiếu máu thiếu sắt",
    "loãng xương", "còi xương",
    "ung thư", "scorbut",
}

KNOWN_NUTRIENTS = {
    "protein", "chất béo", "carbohydrate", "chất xơ",
    "năng lượng", "calories", "calo",
    "canxi", "calcium", "phospho", "sắt", "natri", "kali",
    "magie", "kẽm", "selenium", "đồng", "mangan",
    "vitamin a", "vitamin b1", "vitamin b2", "vitamin b3",
    "vitamin b6", "vitamin b12", "vitamin c", "vitamin d",
    "vitamin e", "vitamin k",
    "beta caroten", "cholesterol", "omega-3", "omega-6",
    "purin", "axit uric", "axit folic", "sắt", "folate",
    "chất béo bão hòa", "chất béo không bão hòa",
    "đường", "đường tinh luyện", "tinh bột",
    "muối", "nước",
}


def classify_entity(name: str, excel_dict: dict) -> str:
    """Classify entity as Food, Disease, Nutrient, or Other."""
    name_lower = name.strip().lower()
    if name_lower in excel_dict:
        return "Food"
    if name_lower in KNOWN_DISEASES:
        return "Disease"
    if name_lower in KNOWN_NUTRIENTS:
        return "Nutrient"
    # Heuristic: nếu tên ngắn và không có số → thường là nutrient hoặc disease
    return "Other"


EXCEL_COL_MAP = {
    "TÊN THỨC ĂN"       : "name",
    "Calories (kcal)"    : "calories",
    "Protein (g)"        : "protein",
    "Fat (g)"            : "fat",
    "Carbonhydrates (g)" : "carbs",
    "Chất xơ (g)"        : "fiber",
    "Cholesterol (mg)"   : "cholesterol",
    "Canxi (mg)"         : "calcium",
    "Photpho (mg)"       : "phosphorus",
    "Sắt (mg)"           : "iron",
    "Natri (mg)"         : "sodium",
    "Kali (mg)"          : "potassium",
    "Beta Caroten (mcg)" : "beta_carotene",
    "Vitamin A (mcg)"    : "vitamin_a",
    "Vitamin B1 (mg)"    : "vitamin_b1",
    "Vitamin C (mg)"     : "vitamin_c",
    "Loại"               : "food_group",
}


def parse_float(val) -> float | None:
    """Convert Vietnamese decimal (comma) or NaN to float."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def load_excel(excel_path: str) -> dict[str, dict]:
    """
    Load Excel → dict { food_name_normalized: {property: value} }
    Key is lowercased + stripped for fuzzy match.
    """
    df = pd.read_excel(excel_path)
    df.rename(columns=EXCEL_COL_MAP, inplace=True)

    food_dict = {}
    for _, row in df.iterrows():
        name = str(row.get("name", "")).strip()
        if not name:
            continue

        props = {"name": name}
        for col in EXCEL_COL_MAP.values():
            if col in ("name", "food_group"):
                continue
            props[col] = parse_float(row.get(col))

        # food_group as string
        props["food_group"] = str(row.get("food_group", "")).strip() or None

        # Index by normalized name
        food_dict[name.lower()] = props

    logger.info(f"📊 Loaded {len(food_dict)} foods from Excel")
    return food_dict


def load_triples(kg_file: str) -> list[list[str]]:
    """Read canon_kg.txt — each line is ['s', 'r', 'o'] or a list of triples."""
    triples = []
    with open(kg_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = ast.literal_eval(line)
                # Line can be a single triple or a list of triples
                if isinstance(parsed, list):
                    if len(parsed) == 3 and isinstance(parsed[0], str):
                        triples.append([str(x) for x in parsed])
                    else:
                        for item in parsed:
                            if isinstance(item, list) and len(item) == 3:
                                triples.append([str(x) for x in item])
            except Exception as e:
                logger.debug(f"Skipping line: {line[:80]} — {e}")
    return triples


def relation_to_cypher_type(relation: str) -> str:
    """Convert Vietnamese relation to valid Neo4j relationship type."""
    # Transliterate common Vietnamese relation words
    mapping = {
        "chứa"               : "CHUA",
        "giàu"               : "GIAU",
        "thuộc nhóm"         : "THUOC_NHOM",
        "làm trầm trọng"     : "LAM_TRAM_TRONG",
        "được khuyến nghị cho": "DUOC_KHUYEN_NGHI_CHO",
        "cần hạn chế ở"      : "CAN_HAN_CHE_O",
        "phòng ngừa"         : "PHONG_NGUA",
        "nhiều"              : "NHIEU",
        "ít"                 : "IT",
        "hỗ trợ"             : "HO_TRO",
        "ảnh hưởng đường huyết": "ANH_HUONG_DUONG_HUYET",
        "chống chỉ định với" : "CHONG_CHI_DINH_VOI",
        "là nguồn"           : "GIAU",   # map về giàu
        "thiếu hụt gây ra"   : "THIEU_HUT_GAY_RA",
        "tương tác với"      : "TUONG_TAC_VOI",
        "là yếu tố nguy cơ của": "LA_YEUTOCUA",
    }
    rel_lower = relation.strip().lower()
    if rel_lower in mapping:
        return mapping[rel_lower]
    # Fallback: strip special chars and uppercase
    cleaned = re.sub(r"[^a-zA-Z0-9\s_]", "", relation)
    return cleaned.strip().upper().replace(" ", "_") or "RELATED_TO"


# ─────────────────────────────────────────────────────────────
# Neo4j Import
# ─────────────────────────────────────────────────────────────

def upsert_entity_node(session, name: str, entity_type: str, props: dict | None, food_label: str):
    """
    Create or update a node with appropriate label based on entity type.
    - Food → label=food_label (e.g. 'Food'), with Excel properties
    - Disease → label='Disease'
    - Nutrient → label='Nutrient'
    - Other → label='Entity'
    """
    label_map = {
        "Food"    : food_label,
        "Disease" : "Disease",
        "Nutrient": "Nutrient",
        "Other"   : "Entity",
    }
    label = label_map.get(entity_type, "Entity")

    if entity_type == "Food" and props:
        set_parts = []
        params = {"name": name}
        for k, v in props.items():
            if k == "name" or v is None:
                continue
            safe_key = k.replace("-", "_")
            set_parts.append(f"n.{safe_key} = ${safe_key}")
            params[safe_key] = v
        set_clause = ", ".join(set_parts)
        query = f"MERGE (n:`{label}` {{name: $name}}) SET n.type = $etype"
        if set_clause:
            query += f", {set_clause}"
        session.run(query, etype=entity_type, **params)
    else:
        session.run(
            f"MERGE (n:`{label}` {{name: $name}}) SET n.type = $etype",
            name=name, etype=entity_type
        )


def import_nutrition(triples, excel_dict, driver, database: str, label: str):
    """
    1. Classify each entity → Food / Disease / Nutrient / Other
    2. Upsert nodes with correct label and properties
    3. Import triples as relationships between nodes
    """
    with driver.session(database=database) as session:
        # Constraints for each label
        for lbl in [label, "Disease", "Nutrient", "Entity"]:
            try:
                session.run(
                    f"CREATE CONSTRAINT {lbl.lower()}_name IF NOT EXISTS "
                    f"FOR (n:`{lbl}`) REQUIRE n.name IS UNIQUE"
                )
            except Exception:
                pass

        # ── Step 1: Classify & upsert all unique entities ────────
        all_entities = set()
        for s, _, o in triples:
            all_entities.add(s)
            all_entities.add(o)

        entity_type_map = {}   # name → (type, label)
        type_counts = {"Food": 0, "Disease": 0, "Nutrient": 0, "Other": 0}

        for entity in all_entities:
            etype = classify_entity(entity, excel_dict)
            props = excel_dict.get(entity.lower()) if etype == "Food" else None
            entity_type_map[entity] = etype
            type_counts[etype] += 1
            upsert_entity_node(session, entity, etype, props, label)

        logger.info(
            f"✅ Upserted {len(all_entities)} entities → "
            f"Food:{type_counts['Food']} | Disease:{type_counts['Disease']} | "
            f"Nutrient:{type_counts['Nutrient']} | Other:{type_counts['Other']}"
        )

        # ── Step 2: Import triples as relationships ──────────────
        success, failed = 0, 0
        label_map = {"Food": label, "Disease": "Disease", "Nutrient": "Nutrient", "Other": "Entity"}

        for s, r, o in triples:
            rel_type = relation_to_cypher_type(r)
            s_label = label_map.get(entity_type_map.get(s, "Other"), "Entity")
            o_label = label_map.get(entity_type_map.get(o, "Other"), "Entity")
            query = (
                f"MATCH (a:`{s_label}` {{name: $subject}}) "
                f"MATCH (b:`{o_label}` {{name: $object}}) "
                f"MERGE (a)-[:`{rel_type}` {{relation: $relation}}]->(b)"
            )
            try:
                session.run(query, subject=s, object=o, relation=r)
                success += 1
            except Exception as e:
                logger.warning(f"Failed triple ({s}, {r}, {o}): {e}")
                failed += 1

        logger.info(f"✅ Imported: {success} triples | Failed: {failed}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Import Nutrition KG + Excel properties into Neo4j")
    parser.add_argument("--kg_file",  required=True,  help="Path to canon_kg.txt (merged or single part)")
    parser.add_argument("--excel",    required=False, default=None,
                        help="Path to food_vietnam_final.xlsx (optional, dùng cho nutrition KG)")
    parser.add_argument("--uri",      default="bolt://localhost:7687")
    parser.add_argument("--user",     default="neo4j")
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--label",    default="Food",
                        help="Node label (default: Food)")
    args = parser.parse_args()

    # Load data
    logger.info(f"Loading KG triples from: {args.kg_file}")
    triples = load_triples(args.kg_file)
    logger.info(f"Total triples: {len(triples)}")

    if args.excel:
        logger.info(f"Loading Excel from: {args.excel}")
        excel_dict = load_excel(args.excel)
    else:
        logger.info("No Excel file provided — skipping food property enrichment.")
        excel_dict = {}

    if not triples:
        logger.warning("No triples found. Exiting.")
        return

    # Connect & import
    logger.info(f"Connecting to Neo4j at {args.uri}...")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))

    try:
        driver.verify_connectivity()
        logger.info("Connection OK.")
        import_nutrition(triples, excel_dict, driver, args.database, args.label)
    finally:
        driver.close()

    print(f"\n📊 Import Summary:")
    print(f"   KG file : {args.kg_file}")
    print(f"   Excel   : {args.excel}")
    print(f"   Triples : {len(triples)}")
    print(f"\n🔍 Cypher để kiểm tra:")
    print(f"   MATCH (f:Food) RETURN f.name, f.protein, f.calories LIMIT 10")
    print(f"   MATCH (f:Food)-[r]->(n) RETURN f.name, type(r), n.name LIMIT 20")


if __name__ == "__main__":
    main()
