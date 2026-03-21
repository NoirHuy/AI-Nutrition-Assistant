# TIẾN ĐỘ DỰ ÁN
# Hệ Thống Tư Vấn Dinh Dưỡng Thông Minh – XÂY DỰNG ĐỒ THỊ TRI THỨC DINH DƯỠNG BỆNH NHÂN

> **Cập nhật lần cuối:** 21/03/2026  
> **Học kỳ:** HK2 (2025–2026)

---

## 📊 TỔNG QUAN TIẾN ĐỘ

| Hạng mục | Tiến độ | Trạng thái |
|----------|---------|-----------|
| Cơ sở hạ tầng (Docker) | 100% | ✅ Hoàn thành |
| Xây dựng Knowledge Graph | 100% | ✅ Hoàn thành |
| Backend API | 100% | ✅ Hoàn thành |
| Frontend | 100% | ✅ Hoàn thành |
| Kiểm thử & Đánh giá | 100% | ✅ Hoàn thành |
| Tài liệu báo cáo | 100% | ✅ Hoàn thành |

**🎉 Tổng tiến độ: 100% – DỰ ÁN ĐÃ HOÀN THÀNH**

---

## ✅ ĐÃ HOÀN THÀNH

### 🏗️ Cơ sở hạ tầng
- [x] Thiết lập Docker Compose với 4 services: `neo4j`, `backend`, `frontend`, `nginx`
- [x] Cấu hình Nginx reverse proxy (port 80 → backend/frontend)
- [x] Kết nối Neo4j từ Backend qua Bolt protocol

### 🧠 Knowledge Graph Pipeline (EDC Framework)
- [x] Tích hợp framework EDC (Extract–Define–Canonicalize)
- [x] Xây dựng dataset y khoa cho 4 nhóm bệnh: Tiểu đường, Tăng huyết áp, Suy thận, Béo phì
- [x] Trích xuất 1000+ Triple quan hệ dinh dưỡng–bệnh lý bằng OIE (Groq LLM)
- [x] Định nghĩa và chuẩn hóa Schema lược đồ bằng Jina Embeddings v3
- [x] Khử trùng lặp thực thể (Cosine Similarity, ngưỡng 0.90)
- [x] Import 500+ món ăn Việt Nam (16 vi chất/món) từ file Excel vào Neo4j
- [x] Hoàn thiện 4 Node Labels: `Food`, `Disease`, `Nutrient`, `Other`
- [x] Hoàn thiện 6 Relation Types: `tốt cho`, `làm trầm trọng`, `là yếu tố nguy cơ của`, `cần hạn chế ở`, `chống chỉ định với`, `chứa`
- [x] Cấu hình Unique Constraints trên Neo4j để chống trùng Node

### ⚙️ Backend API (FastAPI)
- [x] Endpoint `POST /api/chat` — Tư vấn dinh dưỡng qua text
- [x] Endpoint `POST /api/vision` — Nhận diện ảnh + tư vấn (Llama 4 Scout)
- [x] Tích hợp Groq AI (Llama-3.3-70B + Llama-4-Scout-17B)
- [x] Semantic Mapping: LLM ánh xạ từ lóng/địa phương → Node KG chuẩn
- [x] **Circuit Breaker**: Ngắt chuỗi LLM nếu không có dữ liệu trong Neo4j → chống ảo giác 100%
- [x] Cấu hình `.env` quản lý API Keys: `GROQ_API_KEY`, `JINA_KEY`, `NEO4J_*`

### 🎨 Frontend (React + Vite)
- [x] Giao diện Chatbot tư vấn dinh dưỡng
- [x] Dropdown chọn nhóm bệnh lý (4 bệnh)
- [x] Upload & nhận diện ảnh món ăn bằng Vision AI
- [x] Hiển thị lời khuyên định dạng Markdown
- [x] Hiển thị bảng 16 vi chất dinh dưỡng

### 🧪 Kiểm thử & Đánh giá
- [x] Test Case 1: Truy vấn Exact Match (tên đúng trong CSDL)
- [x] Test Case 2: Semantic Mapping (từ lóng/địa phương)
- [x] Test Case 3: Nhận diện ảnh món ăn Việt Nam (Vision AI ~92%)
- [x] Test Case 4: Circuit Breaker (từ chối món ăn ngoài CSDL)

### 📄 Tài liệu báo cáo
- [x] `Chuong1.md` — Giới thiệu đề tài
- [x] `Chuong2.md` — Cơ sở lý thuyết và công nghệ
- [x] `Chuong3.md` — Tổng quan vấn đề nghiên cứu
- [x] `Chuong4.md` — Phân tích & Thiết kế hệ thống (UML: BFD, Use Case, DFD, Class, ERD)
- [x] `Chuong5.md` — Thiết kế CSDL & Use Case mở rộng
- [x] `Chuong6.md` — Đặc tả giao diện
- [x] `Chuong7.md` — Thử nghiệm & Đánh giá
- [x] `Chuong8.md` — Kết luận & Hướng phát triển
- [x] `tailieuthamkhao.md` — Tài liệu tham khảo chuẩn IEEE (13 tài liệu)

---

## 🐛 VẤN ĐỀ ĐÃ GIẢI QUYẾT

| Ngày | Vấn đề | Giải pháp |
|------|--------|-----------|
| 04/02/2026 | ModuleNotFoundError: neo4j | Cài vào đúng `.venv` |
| 04/02/2026 | JSON encode sai ký tự tiếng Việt | Thêm `ensure_ascii=False` |
| 23/02/2026 | Neo4j auth sai sau khi reset DB | Reset container, dùng pass mặc định |
| 23/02/2026 | Graph query sai schema cũ | Cập nhật query dùng label mới |
| 23/02/2026 | Vision API 401 Invalid Key | Cập nhật GROQ_API_KEY mới |
| 23/02/2026 | Từ đồng nghĩa không tìm được trong KG | Thêm Semantic Mapping (LLM ánh xạ → Node KG) |
| 21/03/2026 | AI tư vấn bịa đặt khi món ăn không có trong DB | Triển khai Circuit Breaker – ngắt chuỗi LLM |
| 21/03/2026 | Tài liệu đề cập E5-Mistral không còn dùng | Cập nhật toàn bộ sang Jina Embeddings v3 |
| 21/03/2026 | Dữ liệu Gout còn sót trong codebase | Xóa toàn bộ, thu hẹp phạm vi còn 4 bệnh chính |

---

## 🏁 KẾT QUẢ CUỐI CÙNG

| Chỉ số | Kết quả |
|--------|---------|
| Số Node thực phẩm (Food) | 500+ món ăn Việt Nam |
| Số Node bệnh lý (Disease) | 4 nhóm bệnh mãn tính |
| Số Triple quan hệ y khoa | 1000+ Edges |
| Vi chất dinh dưỡng / món ăn | 16 chỉ số |
| Thời gian phản hồi End-to-End | 1.5 – 2 giây |
| Độ chính xác nhận diện ảnh (Vision) | ~92% |
| Ngăn chặn ảo giác AI (Circuit Breaker) | 100% |

---

*Dự án hoàn thành ngày 21/03/2026. File này không còn cần cập nhật thêm.*
