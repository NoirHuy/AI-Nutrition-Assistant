# HƯỚNG DẪN ĐÁNH GIÁ KNOWLEDGE BASE (KB)
## Đề tài: Xây dựng đồ thị tri thức về dinh dưỡng theo bệnh lý cá nhân

---

## I. TỔNG QUAN CÁC CẤP ĐỘ ĐÁNH GIÁ

| Cấp độ | Mục tiêu | Công cụ | Khi nào dùng |
|--------|----------|---------|--------------|
| **Triple Quality** | Đo độ chính xác từng bộ ba (S, R, O) | Script Python + Gold CSV | Sau khi build xong pipeline |
| **KB Coverage** | Đo độ phủ thực phẩm × bệnh | Cypher trên Neo4j | Kiểm tra định kỳ |
| **End-to-End QA** | Đánh giá chất lượng tư vấn thực tế | Bộ câu hỏi chuẩn | Trước khi demo/báo cáo |

---

## II. ĐÁNH GIÁ CHẤT LƯỢNG TRIPLE (P / R / F1)

### 2.1 Tạo Gold Standard

Tạo file `evaluate/gold_standard.csv` với cấu trúc:

```csv
subject,relation,object,disease_domain,verified_by
chất xơ,hỗ trợ,kiểm soát đường huyết,diabetes,expert
natri,làm trầm trọng,cao huyết áp,hypertension,expert
nội tạng động vật,chống chỉ định với,gút,gout,expert
protein,cần hạn chế ở,suy thận,kidney,expert
chất béo bão hòa,làm trầm trọng,béo phì,obesity,expert
gạo lứt,giàu,chất xơ,nutrition,expert
khoai lang,chứa,beta caroten,nutrition,expert
```

> **Mục tiêu:** Mỗi bệnh tối thiểu 50 triple chuẩn → tổng ~250-300 triple.

### 2.2 Script đánh giá tự động

```python
# evaluate/evaluate_kb.py
import csv
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

def load_gold_standard(gold_csv: str) -> list[dict]:
    with open(gold_csv, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def check_triple_exists(driver, subject: str, relation: str, obj: str) -> bool:
    """Kiểm tra triple có tồn tại trong Neo4j không."""
    rel_type = relation.upper().replace(" ", "_")
    query = f"""
    MATCH (a:Entity {{name: $subject}})-[r:`{rel_type}`]->(b:Entity {{name: $object}})
    RETURN count(r) > 0 AS exists
    """
    with driver.session() as session:
        result = session.run(query, subject=subject, object=obj)
        record = result.single()
        return record["exists"] if record else False

def evaluate(gold_csv: str):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    gold = load_gold_standard(gold_csv)

    tp = 0  # True Positive: triple có trong gold VÀ trong KB
    fn = 0  # False Negative: triple có trong gold nhưng KHÔNG có trong KB

    miss_list = []

    for row in gold:
        found = check_triple_exists(driver, row["subject"], row["relation"], row["object"])
        if found:
            tp += 1
        else:
            fn += 1
            miss_list.append(row)

    driver.close()

    # Tính số triple trong KB (để tính Precision)
    # Precision cần manual review hoặc estimate
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0

    print(f"\n{'='*50}")
    print(f"📊 KẾT QUẢ ĐÁNH GIÁ KB")
    print(f"{'='*50}")
    print(f"Gold Standard triples : {len(gold)}")
    print(f"Tìm thấy trong KB     : {tp}  ✅")
    print(f"Không tìm thấy        : {fn}  ❌")
    print(f"Recall                : {recall:.2%}")
    print(f"\n--- Triple bị thiếu ---")
    for row in miss_list:
        print(f"  [{row['disease_domain']}] ({row['subject']}) --{row['relation']}--> ({row['object']})")

if __name__ == "__main__":
    evaluate("./evaluate/gold_standard.csv")
```

**Chạy:**
```bash
python evaluate/evaluate_kb.py
```

---

## III. ĐÁNH GIÁ ĐỘ PHỦ CỦA KB (Coverage)

Chạy các lệnh Cypher sau trong Neo4j Browser (`http://localhost:7474`):

### 3.1 Thống kê tổng quan
```cypher
// Tổng số node và relationship
MATCH (n) RETURN count(n) AS total_nodes
MATCH ()-[r]->() RETURN count(r) AS total_relationships
```

### 3.2 Coverage theo bệnh
```cypher
MATCH (f:Entity)-[r]->(d:Entity)
WHERE d.name IN ["tiểu đường", "cao huyết áp", "gút", "béo phì", "suy thận"]
RETURN d.name AS disease, type(r) AS relation, count(*) AS count
ORDER BY disease, count DESC
```

### 3.3 Coverage theo loại quan hệ
```cypher
MATCH ()-[r]->()
RETURN type(r) AS relation_type, count(*) AS count
ORDER BY count DESC
```

### 3.4 Tìm thực phẩm có đủ liên kết cho tất cả 5 bệnh
```cypher
MATCH (f:Entity)-[r]->(d:Entity)
WHERE d.name IN ["tiểu đường", "cao huyết áp", "gút", "béo phì", "suy thận"]
WITH f, count(DISTINCT d.name) AS disease_count
WHERE disease_count = 5
RETURN f.name AS food, disease_count
ORDER BY food
```

---

## IV. ĐÁNH GIÁ END-TO-END (QA Benchmark)

### 4.1 Bộ câu hỏi chuẩn (mẫu)

Tạo file `evaluate/qa_benchmark.csv`:

```csv
question,disease,expected_food_avoid,expected_food_recommend
Người bệnh gút nên tránh ăn gì?,gout,"nội tạng động vật,hải sản,bia,thịt đỏ","rau xanh,trái cây,nước"
Người cao huyết áp cần hạn chế chất nào?,hypertension,"natri,muối,rượu bia","kali,magie,omega-3"
Người tiểu đường nên ăn gì?,diabetes,"đường tinh luyện,gạo trắng","gạo lứt,rau xanh,chất xơ"
Người suy thận cần tránh gì?,kidney,"protein cao,phốt pho,kali cao","lòng trắng trứng,rau ít kali"
Người béo phì nên tránh gì?,obesity,"chất béo bão hòa,đường,đồ ăn nhanh","rau xanh,chất xơ,protein nạc"
```

### 4.2 Quy trình đánh giá QA

```
1. Với mỗi câu hỏi → gửi vào GraphRAG backend
2. Nhận danh sách thực phẩm/dưỡng chất từ KB
3. So sánh với expected_food_avoid / expected_food_recommend
4. Tính Hit Rate@5 (có ít nhất 1 kết quả đúng trong top 5 không)
5. Tính Precision@K và Recall@K
```

---

## V. CHỈ SỐ BÁO CÁO

Khi báo cáo đồ án, trình bày các chỉ số sau:

| Chỉ số | Mục tiêu tối thiểu | Ghi chú |
|--------|-------------------|---------|
| Recall (Triple) | ≥ 70% | So với Gold Standard |
| KB Coverage (node) | ≥ 150 thực phẩm | Dữ liệu thực phẩm Việt Nam |
| KB Coverage (bệnh) | 5/5 bệnh | Đủ quan hệ cho cả 5 bệnh |
| Relation types | ≥ 8 loại | Dùng đủ các quan hệ trong schema |
| QA Hit Rate@5 | ≥ 80% | Câu hỏi tư vấn cơ bản |

---

## VI. THỨ TỰ THỰC HIỆN ĐỂ ĐÁNH GIÁ

```
Bước 1: Build KB hoàn chỉnh (chạy pipeline cho mọi bộ dữ liệu)
         ↓
Bước 2: Chạy lệnh Cypher → kiểm tra coverage
         ↓
Bước 3: Tạo Gold Standard CSV (nhờ chuyên gia xác nhận hoặc tự tổng hợp)
         ↓
Bước 4: Chạy evaluate_kb.py → tính Recall
         ↓
Bước 5: Chạy 25 câu hỏi QA benchmark → tính Hit Rate
         ↓
Bước 6: Tổng hợp kết quả → đưa vào báo cáo đồ án
```

---

## VII. GHI CHÚ

- **Precision** khó đo tự động vì cần con người verify từng triple trong KB.
  → Có thể sample ngẫu nhiên 50 triple từ KB → nhờ chuyên gia đánh giá → tính Precision thủ công.
- **Recall** dễ đo tự động bằng script trên (so với Gold Standard).
- Nếu Recall thấp → pipeline đang bỏ sót nhiều triple → cần review lại few-shot hoặc schema.
- Nếu Precision thấp → pipeline đang sinh ra triple sai → cần cải thiện OIE prompt hoặc thêm postprocess_fix.
