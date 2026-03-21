import os
import ast
import re
import argparse
import logging
import numpy as np
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# =====================================================================
# BƯỚC 1: QUY TẮC LỌC RÁC & CHUẨN HÓA (Theo đặc thù Bệnh lý / Dinh dưỡng)
# =====================================================================

KNOWN_NUTRIENTS = {
    "protein", "chất béo", "carbohydrate", "chất xơ", "năng lượng",
    "canxi", "phospho", "sắt", "natri", "kali", "beta caroten",
    "vitamin b1", "vitamin b2", "vitamin c", "vitamin a", "vitamin d",
    "vitamin k", "cholesterol", "purin", "đường", "muối",
    "magie", "kẽm", "đồng", "selen", "iốt", "folate",
    "axit béo", "axit béo bão hòa", "axit béo trans", "axit béo không bão hòa",
    "axit béo không bão hòa đa", "axit béo không bão hòa đơn",
    "mufa", "pufa", "omega-3", "omega-6", "glucose", "fructose",
    "chất béo bão hòa", "chất béo không bão hòa", "axit uric",
    "lipid", "tinh bột", "đường tinh luyện", "đường bổ sung",
    "fiber", "fat", "sugar", "sodium", "calcium", "iron", "potassium",
}

INVERTED_RELATIONS = {"giàu", "chứa", "nhiều", "ít"}

ABSTRACT_SUBJECT_PREFIXES = [
    "hướng dẫn", "liệu pháp", "mô hình", "đếm", "phương pháp",
    "chương trình", "kế hoạch", "chiến lược", "can thiệp",
    "nghiên cứu", "bằng chứng", "khuyến cáo", "hội",
]

ABSTRACT_SUBJECT_EXACT = {
    "hoạt động thể chất", "giảm cân", "liệu pháp ăn kiêng",
    "liệu pháp dinh dưỡng cá thể hóa", "liệu pháp dinh dưỡng",
    "carcinogens", "người bệnh", "tình trạng", "bệnh nhân", 
    "người mắc bệnh", "tình trạng bệnh", "sức khỏe"
}

GENERIC_OBJECTS = {
    "sức khỏe", "chế độ ăn uống", "chế độ ăn", "chế độ ăn kiêng",
    "chế độ ăn uống hàng ngày", "chế độ ăn uống lành mạnh",
    "tiêu thụ protein", "tiêu thụ carbohydrate",
    "tiêu thụ vitamin", "tiêu thụ khoáng chất",
    "xác định nồng độ insulin",
    "duy trì trọng lượng khỏe mạnh",
    "giảm nguy cơ bệnh tim mạch",
    "người bệnh", "cơ thể", "thể trạng",
}

# ĐÃ NÂNG CẤP: Chuyển thành bộ từ điển đồng nghĩa mạnh mẽ hơn
ABBREVIATION_MAP = {
    # Nhóm Thận
    "dkd": "suy thận do tiểu đường",
    "ckd": "suy thận",
    "suy thận mãn tính": "suy thận",
    "bệnh suy thận": "suy thận",
    
    # Nhóm Tiêu hóa
    "gerd": "trào ngược dạ dày thực quản",
    
    # Nhóm Tim mạch & Huyết áp
    "cvd": "bệnh tim mạch",
    "htn": "tăng huyết áp",
    "tha": "tăng huyết áp",
    "bệnh tha": "tăng huyết áp",
    "người bệnh tha": "tăng huyết áp",
    "cao huyết áp": "tăng huyết áp",
    "bệnh tăng huyết áp": "tăng huyết áp",
    
    # Nhóm Tiểu đường
    "dm": "tiểu đường",
    "t2dm": "tiểu đường tuýp 2",
    "đái tháo đường": "tiểu đường",
    "bệnh tiểu đường": "tiểu đường",
    "người bệnh tiểu đường": "tiểu đường",
    
    # Nhóm Béo phì / Chuyển hóa
    "bệnh béo phì": "béo phì",
    "người béo phì": "béo phì",
    "người thừa cân béo phì": "béo phì",
    
    # Nhóm Gout
    "bệnh gút": "gout",
    "người bệnh gút": "gout",
    "bệnh gout": "gout",
    "người bệnh gout": "gout",
    "kiểm soát bệnh gout": "gout" 
}

def is_abstract_subject(s: str) -> bool:
    s_lower = s.strip().lower()
    if s_lower in ABSTRACT_SUBJECT_EXACT:
        return True
    for prefix in ABSTRACT_SUBJECT_PREFIXES:
        if s_lower.startswith(prefix):
            return True
    return False

def is_generic_object(o: str) -> bool:
    return o.strip().lower() in GENERIC_OBJECTS

def normalize_abbreviation(entity: str) -> str:
    # Tra cứu trong từ điển, nếu không có thì trả về tên gốc
    return ABBREVIATION_MAP.get(entity.strip().lower(), entity)

def is_nutrient(name: str) -> bool:
    return name.strip().lower() in KNOWN_NUTRIENTS

def fix_inverted_relation(s: str, r: str, o: str):
    if r.lower() in INVERTED_RELATIONS and is_nutrient(s) and not is_nutrient(o):
        logger.info(f"  [ĐẢO CHIỀU] ({s!r}, {r!r}, {o!r}) → ({o!r}, {r!r}, {s!r})")
        return o, r, s
    return s, r, o


# =====================================================================
# BƯỚC 2: OIE TRIPLE EXTRACTION LÀM SẠCH (RULE-BASED)
# =====================================================================

def load_canon_kg(path: str) -> list[list[str]]:
    triples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                parsed = ast.literal_eval(line)
                if not isinstance(parsed, list): continue
                if len(parsed) == 3 and isinstance(parsed[0], str):
                    triples.append([str(x) for x in parsed])
                else:
                    for item in parsed:
                        if isinstance(item, list) and len(item) == 3:
                            triples.append([str(x) for x in item])
            except Exception as e:
                pass
    return triples

def preliminary_clean_triples(raw_triples: list[list[str]]) -> list[list[str]]:
    """Loại bỏ rác do LLM sinh ra (các node chung chung, bị đảo mũi tên)"""
    cleaned = []
    seen = set()

    for s, r, o in raw_triples:
        s, o, r = s.strip(), o.strip(), r.strip()
        
        # 1. Xử lý đồng nghĩa & viết tắt TRƯỚC (để gom nhóm dễ hơn)
        s = normalize_abbreviation(s)
        o = normalize_abbreviation(o)

        # 2. Bỏ Subject trừu tượng & Object tào lao (như 'bệnh nhân', 'sức khỏe')
        if is_abstract_subject(s) or is_generic_object(o):
            continue

        # 3. Đảo chiều mũi tên lỗi
        s, r, o = fix_inverted_relation(s, r, o)

        # 4. Tránh lặp hoàn toàn
        key = (s.lower(), r.lower(), o.lower())
        if key not in seen:
            seen.add(key)
            cleaned.append([s, r, o])
            
    return cleaned

# =====================================================================
# BƯỚC 3: DEDUPLICATION BẰNG JINA EMBEDDINGS (SEMANTIC CLUSTERING)
# =====================================================================

def get_jina_embeddings(texts: list[str], jina_key: str, model: str = "jina-embeddings-v3") -> np.ndarray:
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

def normalize_entity_for_embedding(entity: str) -> str:
    return entity.lower().replace("_", " ").strip()

def build_entity_clusters(entities: list[str], embeddings: np.ndarray, threshold: float = 0.90) -> dict[str, str]:
    n = len(entities)
    canonical_map = {}
    clusters = [] 

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
            
    return canonical_map

def semantic_deduplicate(triples: list[list[str]], similarity_threshold: float, jina_key: str) -> list[list[str]]:
    """Nhóm các thực thể gọi khác tên (ví dụ: tiểu_đường & bệnh_tiểu_đường)"""
    all_entities_raw = set()
    for s, r, o in triples:
        all_entities_raw.add(s)
        all_entities_raw.add(o)

    all_entities = list(all_entities_raw)
    if len(all_entities) == 0:
        return triples

    normalized = [normalize_entity_for_embedding(e) for e in all_entities]

    logger.info(f"Đang lấy Jina embeddings cho {len(normalized)} thực thể duy nhất...")
    batch_size = 50
    all_embeddings = []
    for i in range(0, len(normalized), batch_size):
        batch = normalized[i : i + batch_size]
        all_embeddings.append(get_jina_embeddings(batch, jina_key))
    embeddings = np.vstack(all_embeddings)

    logger.info("Clustering thực thể tương đồng bằng ma trận Cosine Similarity...")
    canonical_map = build_entity_clusters(all_entities, embeddings, threshold=similarity_threshold)

    deduped_triples = []
    seen = set()
    for s, r, o in triples:
        s_canon = canonical_map.get(s, s)
        o_canon = canonical_map.get(o, o)
        
        # Bỏ qua vòng lặp tự thân (Self-loop) như: "Mỡ" -> "Mỡ"
        if s_canon == o_canon:
            continue
            
        triple_key = (s_canon, r, o_canon)
        if triple_key not in seen:
            deduped_triples.append([s_canon, r, o_canon])
            seen.add(triple_key)

    return deduped_triples

# =====================================================================
# MAIN PIPELINE
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Pipeline Hậu Xử Lý KG: Làm sạch tĩnh (Rule-based) & Khử trùng lặp AI (Embeddings)")
    parser.add_argument("--input_file", required=True, help="Đường dẫn file canon_kg.txt ban đầu")
    parser.add_argument("--output_file", required=True, help="Đường dẫn file kg_clean.txt đầu ra cuổi")
    parser.add_argument("--similarity_threshold", type=float, default=0.90, help="Độ nhạy khử trùng lặp (Mặc định: 0.90)")
    args = parser.parse_args()

    jina_key = os.environ.get("JINA_KEY", "")
    if not jina_key:
        logger.error("JINA_KEY không được đặt. Vui lòng set biến môi trường JINA_KEY để chạy thuật toán Vector.")
        return

    logger.info(f"Đang đọc file Triples thô: {args.input_file}...")
    raw_triples = load_canon_kg(args.input_file)
    logger.info(f"Tổng số Triples thô: {len(raw_triples)}")

    logger.info("--- BƯỚC 1: Tiền lọc Rule-Based (Gỡ bỏ trừu tượng & Đảo chiều quan hệ) ---")
    cleaned_triples = preliminary_clean_triples(raw_triples)
    logger.info(f"Số Triples còn lại sau khi đi qua màng lọc Tĩnh: {len(cleaned_triples)}")

    logger.info("--- BƯỚC 2: Khử trùng lặp thực thể bằng Trí tuệ nhân tạo (Jina Embeddings) ---")
    final_triples = semantic_deduplicate(cleaned_triples, args.similarity_threshold, jina_key)
    logger.info(f"Số Triples tinh hoa cuối cùng: {len(final_triples)}")

    os.makedirs(os.path.dirname(os.path.abspath(args.output_file)), exist_ok=True)
    with open(args.output_file, "w", encoding="utf-8") as f:
        for triple in final_triples:
            f.write(str(triple) + "\n")

    logger.info(f"✅ HOÀN TẤT. Graph đã cực kỳ sạch, có thể Import vào Neo4j ngay lập tức (Lưu tại: {args.output_file})")


if __name__ == "__main__":
    main()