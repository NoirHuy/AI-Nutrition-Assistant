# BÁO CÁO TỔNG QUÁT DỰ ÁN
# Hệ Thống Tư Vấn Dinh Dưỡng Thông Minh Dựa Trên Đồ Thị Tri Thức

> **Đồ Án 2 — HK2 (2025–2026)**

---

## 1. TỔNG QUAN DỰ ÁN

### 1.1. Mục Tiêu

Xây dựng hệ thống tư vấn dinh dưỡng cá nhân hóa theo bệnh lý, bao gồm hai thành phần chính:

1. **Pipeline xây dựng Đồ Thị Tri Thức (Knowledge Graph — KG)**: Tự động trích xuất tri thức dinh dưỡng-bệnh lý từ văn bản y khoa tiếng Anh, dịch sang tiếng Việt và lưu trữ vào Neo4j.
2. **Ứng dụng tư vấn trực tiếp**: Chatbot + nhận diện ảnh món ăn, truy vấn KG để đưa ra lời khuyên dinh dưỡng phù hợp với tình trạng bệnh của người dùng.

### 1.2. Bệnh Lý Được Hỗ Trợ

Hệ thống đã xây dựng KG cho **10 bệnh lý** chuyển hóa và dinh dưỡng phổ biến:

| STT | Bệnh lý |
|-----|---------|
| 1 | Tiểu đường type 2 (Diabetes) |
| 2 | Tăng huyết áp (Hypertension) |
| 3 | Bệnh thận mãn tính (Chronic Kidney Disease) |
| 4 | Thiếu máu thiếu sắt (Iron Deficiency Anemia) |
| 5 | Bệnh Celiac (Gluten Intolerance) |
| 6 | Bệnh Gout |
| 7 | Loãng xương (Osteoporosis) |
| 8 | Gan nhiễm mỡ (Fatty Liver Disease) |
| 9 | Bệnh tuyến giáp (Thyroid Disease) |
| 10 | Phenylketon niệu (PKU) |

---

## 2. KIẾN TRÚC HỆ THỐNG

```
┌─────────────────────────────────────────────────────────────┐
│                    NGƯỜI DÙNG (Browser)                     │
│              React/Vite  •  Port 5173                       │
└──────────────────────┬──────────────────────────────────────┘
                       │  HTTP via Nginx (Port 80)
┌──────────────────────▼──────────────────────────────────────┐
│                  NGINX GATEWAY  •  Port 80                  │
│         Reverse Proxy → Backend/Frontend                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│               FASTAPI BACKEND  •  Port 8000                 │
│  /api/chat   → Tư vấn bằng text                            │
│  /api/vision → Nhận diện ảnh + tư vấn                      │
│                                                             │
│  ai_chat.py      → Groq AI (Llama-4 + GPT-OSS-120B)       │
│  graph_query.py  → Truy vấn Neo4j                          │
│  import_food.py  → Nhập dữ liệu thực phẩm                 │
└──────────────────────┬──────────────────────────────────────┘
                       │  bolt://7687
┌──────────────────────▼──────────────────────────────────────┐
│            NEO4J GRAPH DATABASE  •  Port 7474/7687          │
│  Label: TieuDuongKG   → KG tiếng Việt (39 triples)        │
│  Label: TieuDuongKG_EN → KG tiếng Anh (39 triples)        │
│  Food nodes           → Dữ liệu thực phẩm Việt Nam        │
└─────────────────────────────────────────────────────────────┘
```

**Docker Compose** quản lý toàn bộ 4 services: `nutrition_graph`, `nutrition_backend`, `nutrition_frontend`, `nutrition_gateway`.

---

## 3. PIPELINE XÂY DỰNG KNOWLEDGE GRAPH

### 3.1. Framework EDC (Extract–Define–Canonicalize)

Sử dụng framework **EDC** để tự động trích xuất KG từ văn bản y khoa theo 3 pha:

```
Văn bản y khoa (tiếng Anh)
         │
         ▼
┌────────────────────┐
│  Phase 1: OIE      │  Open Information Extraction
│  Groq Llama-3.3-70B│  → Trích xuất bộ ba (S, R, O) thô
└─────────┬──────────┘
          ▼
┌────────────────────┐
│  Phase 2: SD       │  Schema Definition
│  Groq Llama-3.3-70B│  → Định nghĩa ngữ nghĩa quan hệ
└─────────┬──────────┘
          ▼
┌────────────────────┐
│  Phase 3: SC       │  Schema Canonicalization
│  Jina Embeddings v3│  → Ánh xạ vào 15 quan hệ chuẩn
│  + Groq LLM verify │
└─────────┬──────────┘
          ▼
    kg_raw.txt → (dedup) → kg_deduplicated.txt
         │
         ▼ (dịch sang tiếng Việt)
    kg_vi.txt → Neo4j (label: TieuDuongKG)
```

### 3.2. Schema 15 Quan Hệ Chuẩn

| Quan hệ | Ý nghĩa (tiếng Việt) |
|---------|----------------------|
| `treats` | hỗ trợ điều trị |
| `prevents` | phòng ngừa |
| `aggravates` | làm trầm trọng |
| `recommended_for` | được khuyến nghị cho |
| `contraindicated_for` | chống chỉ định với |
| `deficiency_causes` | thiếu hụt gây ra |
| `enhances_absorption_of` | tăng cường hấp thu |
| `restricts` | cần hạn chế ở |
| `requires` | cần bổ sung ở |
| `contains` | cung cấp |
| `reduces` | làm giảm |
| `increases` | làm tăng |
| `associated_with` | là yếu tố nguy cơ của |
| `daily_intake` | lượng khuyến nghị |
| `food_source` | nguồn thực phẩm |
| `symptom_of` | là triệu chứng của |

### 3.3. Các Script Chính (thư mục `edc-main/`)

| Script | Chức năng |
|--------|-----------|
| `preprocess_document_en.py` | Tiền xử lý văn bản y khoa tiếng Anh |
| `run.py` | Chạy pipeline EDC (OIE → SD → SC) |
| `postprocess_kg_en.py` | Deduplication thực thể bằng Jina Embeddings |
| `translate_kg_to_neo4j.py` | Dịch KG sang tiếng Việt (Groq) + import Neo4j |
| `import_to_neo4j.py` | Import KG trực tiếp vào Neo4j |

---

## 4. BACKEND API (FastAPI)

### 4.1. Endpoints

| Endpoint | Method | Chức năng |
|----------|--------|-----------|
| `/` | GET | Health check |
| `/api/chat` | POST | Tư vấn dinh dưỡng qua text |
| `/api/vision` | POST | Nhận diện ảnh món ăn + tư vấn |

### 4.2. Luồng Xử Lý Vision API

```
Ảnh món ăn (base64)
       │
       ▼
Llama-4 Maverick (Groq)
→ Nhận diện tên món (VD: "Phở bò")
       │
       ▼
Neo4j graph_query
→ Lấy thành phần dinh dưỡng của món
→ Lấy quy tắc cấm theo bệnh
       │
       ▼
GPT-OSS-120B (Groq)
→ Phân tích, so sánh, tạo lời khuyên Markdown
```

### 4.3. Mô Hình AI Sử Dụng

| Mô hình | Nhà cung cấp | Dùng cho |
|---------|-------------|----------|
| `llama-3.3-70b-versatile` | Groq | KG Extraction + Translation |
| `meta-llama/llama-4-maverick-17b-128e-instruct` | Groq | Nhận diện ảnh (Vision) |
| `openai/gpt-oss-120b` | Groq | Tư vấn dinh dưỡng |
| `jina-embeddings-v3` | Jina AI | Schema Canonicalization |

---

## 5. FRONTEND (React + Vite)

- **Framework**: React 18 + Vite
- **Port**: 5173
- **Tính năng**:
  - Chọn bệnh lý của người dùng
  - Chatbox tư vấn dinh dưỡng
  - Upload ảnh món ăn để phân tích

---

## 6. CƠ SỞ DỮ LIỆU NEO4J

### 6.1. Thông tin kết nối

| Thông số | Giá trị |
|----------|---------|
| URI | `bolt://localhost:7687` |
| Browser | `http://localhost:7474` |
| User | `neo4j` |
| Password | `password` |
| Version | `5.16.0` |

### 6.2. Dữ liệu hiện có

| Label | Số triples | Mô tả |
|-------|-----------|-------|
| `TieuDuongKG` | 39 | KG tiếng Việt (đã dịch) |
| `TieuDuongKG_EN` | 39 | KG tiếng Anh gốc |

### 6.3. Câu truy vấn kiểm tra

```cypher
// Xem toàn bộ KG tiếng Việt
MATCH (n:TieuDuongKG)-[r]->(m:TieuDuongKG)
RETURN n.name, type(r), m.name
LIMIT 50

// Đếm số node
MATCH (n:TieuDuongKG) RETURN count(n)
```

---

## 7. CÔNG NGHỆ & THƯ VIỆN

### 7.1. KG Pipeline

| Thư viện | Phiên bản | Dùng cho |
|----------|-----------|----------|
| `openai` | latest | Gọi Groq API |
| `groq` | latest | Groq Python SDK |
| `neo4j` | latest | Driver kết nối Neo4j |
| `numpy` | latest | Tính cosine similarity |
| `requests` | latest | Gọi Jina Embeddings API |

### 7.2. Backend

| Thư viện | Dùng cho |
|----------|----------|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `pydantic` | Data validation |
| `groq` | AI API client |
| `neo4j` | Graph database driver |
| `openpyxl` | Đọc file Excel thực phẩm |

### 7.3. Infrastructure

| Công nghệ | Dùng cho |
|-----------|----------|
| Docker + Docker Compose | Container orchestration |
| Nginx | Reverse proxy / API Gateway |
| Neo4j 5.16.0 Community | Graph database |

---

## 8. CẤU TRÚC THƯ MỤC

```
MyProject/
├── docker-compose.yml          # Orchestration 4 services
├── nginx/
│   └── default.conf            # Nginx reverse proxy config
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI app + endpoints
│       ├── config.py           # ENV variables
│       ├── database.py         # Neo4j connection
│       └── services/
│           ├── ai_chat.py      # Groq AI integration
│           ├── graph_query.py  # Neo4j queries
│           └── import_food.py  # Food data importer
├── frontend-diet/
│   └── src/                    # React components
├── neo4j_data/                 # Neo4j volume (data)
└── edc-main/                   # KG Builder Pipeline
    ├── datasets/               # Văn bản y khoa đầu vào
    ├── schemas/                # Schema 15 quan hệ (CSV)
    ├── few_shot_examples/      # Few-shot prompts
    ├── edc/                    # EDC framework core
    ├── output/                 # KG output files
    │   └── diabetes_en_kg/
    │       └── iter0/
    │           ├── kg_deduplicated.txt  # KG tiếng Anh
    │           └── kg_vi.txt            # KG tiếng Việt
    ├── preprocess_document_en.py
    ├── postprocess_kg_en.py
    ├── translate_kg_to_neo4j.py
    └── import_to_neo4j.py
```

---

## 9. HƯỚNG DẪN CHẠY DỰ ÁN

### 9.1. Yêu cầu

- Docker Desktop đang chạy
- Python 3.11+ + `.venv` đã cài đặt
- File `.env` với `GROQ_KEY` (để chạy KG pipeline)

### 9.2. Khởi động toàn bộ hệ thống

```bash
# Từ thư mục MyProject/
docker-compose up -d
```

Sau đó truy cập:
- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **Neo4j Browser**: http://localhost:7474

### 9.3. Chạy lại KG Pipeline (nếu cần)

```powershell
# 1. Tiền xử lý văn bản
cd edc-main
python preprocess_document_en.py --input datasets/diabetes_en.txt

# 2. Trích xuất KG (EDC)
python run.py --dataset diabetes_en --iterations 1

# 3. Deduplication
python postprocess_kg_en.py

# 4. Dịch + Import vào Neo4j
python translate_kg_to_neo4j.py

# Hoặc chỉ import KG đã có
python import_to_neo4j.py `
  --kg_file "./output/diabetes_en_kg/iter0/kg_vi.txt" `
  --uri "bolt://localhost:7687" `
  --user "neo4j" --password "password" `
  --label "TieuDuongKG"
```

---

## 10. KẾT QUẢ ĐẠT ĐƯỢC

| Hạng mục | Kết quả |
|----------|---------|
| KG triples đã trích xuất | 39 (bệnh tiểu đường) |
| KG đã dịch sang tiếng Việt | ✅ 39 triples |
| Import thành công vào Neo4j | ✅ 0 lỗi |
| Backend API hoạt động | ✅ /api/chat + /api/vision |
| Frontend triển khai | ✅ React + Vite |
| Containerization | ✅ Docker Compose 4 services |
| Vision AI (nhận diện ảnh) | ✅ Llama-4 Maverick |
| Tư vấn dinh dưỡng | ✅ GPT-OSS-120B + Neo4j RAG |

---

*Báo cáo được tạo ngày: 23/02/2026*
