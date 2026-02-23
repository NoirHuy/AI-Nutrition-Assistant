# TIẾN ĐỘ DỰ ÁN
# Hệ Thống Tư Vấn Dinh Dưỡng Thông Minh (AI Nutrition Assistant)

> **Cập nhật lần cuối:** 23/02/2026  
> **Học kỳ:** HK2 (2025–2026)

---

## 📊 TỔNG QUAN TIẾN ĐỘ

| Hạng mục | Tiến độ | Trạng thái |
|----------|---------|-----------|
| Cơ sở hạ tầng (Docker) | 100% | ✅ Hoàn thành |
| Xây dựng Knowledge Graph | 60% | 🔄 Đang làm |
| Backend API | 85% | 🔄 Đang làm |
| Frontend | 70% | 🔄 Đang làm |
| Kiểm thử & Tối ưu | 30% | ⏳ Chưa đủ |
| Tài liệu | 80% | 🔄 Đang làm |

**Tổng tiến độ ước tính: ~65%**

---

## ✅ ĐÃ HOÀN THÀNH

### 🏗️ Cơ sở hạ tầng
- [x] Thiết lập Docker Compose với 4 services: `neo4j`, `backend`, `frontend`, `nginx`
- [x] Cấu hình Nginx reverse proxy (port 80 → backend/frontend)
- [x] Kết nối Neo4j từ Backend qua Bolt protocol

### 🧠 Knowledge Graph Pipeline (EDC Framework)
- [x] Tích hợp framework EDC (Extract–Define–Canonicalize)
- [x] Viết script tiền xử lý văn bản tiếng Anh (`preprocess_document_en.py`)
- [x] Viết script hậu xử lý & deduplication (`postprocess_kg_en.py`) bằng Jina Embeddings
- [x] Xây dựng dataset tiểu đường tiếng Anh (`datasets/diabetes_en.txt`)
- [x] Định nghĩa schema 15 quan hệ dinh dưỡng-bệnh lý (`schemas/nutrition_schema.csv`)
- [x] Trích xuất KG cho bệnh tiểu đường (39 triples)
- [x] Dịch KG sang tiếng Việt bằng Groq LLM (`translate_kg_to_neo4j.py`)
- [x] Import KG vào Neo4j với label `TieuDuongKG` (39 triples tiếng Việt)
- [x] Import KG tiếng Anh với label `TieuDuongKG_EN` (39 triples)

### ⚙️ Backend API (FastAPI)
- [x] Endpoint `POST /api/chat` — Tư vấn dinh dưỡng qua text
- [x] Endpoint `POST /api/vision` — Nhận diện ảnh + tư vấn
- [x] Tích hợp Groq AI (Llama-3.3-70B + Llama-4 Maverick)
- [x] Truy vấn Neo4j theo schema mới (`TieuDuongKG`)
- [x] **Semantic Mapping**: LLM ánh xạ input người dùng → node KG
  - VD: "nước ngọt có ga" → `đồ_uống_có_đường`
- [x] Response format: Tên món → Lời khuyên (LLM) → Dữ liệu KG

### 🎨 Frontend (React + Vite)
- [x] Giao diện chatbot tư vấn dinh dưỡng
- [x] Chức năng chọn bệnh lý
- [x] Upload & phân tích ảnh món ăn
- [x] Hiển thị kết quả định dạng Markdown

### 📄 Tài liệu
- [x] `README.md` — Tổng quan & kiến trúc hệ thống (Chương 1)
- [x] `BÁO_CÁO_DỰ_ÁN.md` — Báo cáo tổng quát

---

## 🔄 ĐANG THỰC HIỆN

### 🧠 Knowledge Graph
- [ ] Mở rộng KG cho các bệnh còn lại (9 bệnh chưa có KG)
  - [ ] Tăng huyết áp (Hypertension)
  - [ ] Bệnh thận mãn tính
  - [ ] Thiếu máu thiếu sắt
  - [ ] Bệnh Celiac
  - [ ] Bệnh Gout
  - [ ] Loãng xương
  - [ ] Gan nhiễm mỡ
  - [ ] Bệnh tuyến giáp
  - [ ] Phenylketon niệu (PKU)
- [ ] Tăng số lượng triples (hiện tại chỉ 39, cần ít nhất 200+)
- [ ] Import dữ liệu thực phẩm Việt Nam vào KG (Food nodes)

### ⚙️ Backend
- [ ] Kiểm thử độ chính xác của Semantic Mapping
- [ ] Xử lý trường hợp bệnh ngoài KG (fallback graceful)
- [ ] Thêm caching để giảm số lần gọi Neo4j

### 🎨 Frontend
- [ ] Cải thiện UX hiển thị kết quả
- [ ] Thêm loading state khi đang xử lý ảnh

---

## ⏳ CHƯA BẮT ĐẦU

### 🧪 Kiểm thử & Đánh giá
- [ ] Viết test cases cho các scenario tư vấn
- [ ] Đánh giá độ chính xác KG (Precision / Recall)
- [ ] Kiểm thử với các câu hỏi thực tế từ người dùng
- [ ] So sánh kết quả KG-grounded vs LLM hallucination

### 📄 Tài liệu còn lại
- [ ] Chương 2: Phương pháp nghiên cứu
- [ ] Chương 3: Kết quả thực nghiệm
- [ ] Chương 4: Kết luận & hướng phát triển
- [ ] Slide thuyết trình

---

## 🐛 VẤN ĐỀ ĐÃ GIẢI QUYẾT

| Ngày | Vấn đề | Giải pháp |
|------|--------|-----------|
| 04/02/2026 | ModuleNotFoundError: neo4j | Cài vào đúng `.venv` |
| 04/02/2026 | JSON encode sai ký tự tiếng Việt | Thêm `ensure_ascii=False` |
| 23/02/2026 | Neo4j auth sai sau khi reset DB | Reset container, dùng pass mặc định `password` |
| 23/02/2026 | Graph query sai schema cũ (Disease/Food) | Cập nhật query dùng label `TieuDuongKG` |
| 23/02/2026 | Vision API 401 Invalid Key | Cập nhật GROQ_API_KEY mới |
| 23/02/2026 | "nước ngọt có ga" không tìm được trong KG | Thêm Semantic Mapping (LLM ánh xạ → node KG) |

---

## 📅 KẾ HOẠCH TIẾP THEO

| Tuần | Mục tiêu |
|------|---------|
| Tuần tới | Mở rộng KG thêm 3-4 bệnh (Hypertension, CKD, Anemia) |
| Tuần tới | Import dữ liệu thực phẩm Việt Nam (100+ món) |
| Sau đó | Kiểm thử hệ thống end-to-end |
| Trước bảo vệ | Hoàn thiện tài liệu & slide |

---

*File này cập nhật thủ công theo tiến độ thực tế của dự án.*
