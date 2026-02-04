# 🥗 AI Nutrition Assistant - Trợ lý Dinh dưỡng & Thị giác Máy tính

![Project Banner](https://via.placeholder.com/1200x400?text=AI+Nutrition+Assistant+Project)

> **Đồ án Môn học:** Xây dựng hệ thống tư vấn dinh dưỡng cá nhân hóa dựa trên Đồ thị tri thức (Knowledge Graph) và AI tạo sinh (Generative AI).

## 📖 Giới thiệu

**AI Nutrition Assistant** là ứng dụng web giúp người dùng, đặc biệt là bệnh nhân mắc các bệnh lý mãn tính (Tiểu đường, Cao huyết áp, Gout...), dễ dàng kiểm tra độ an toàn của món ăn.

Hệ thống kết hợp **Computer Vision** để nhận diện món ăn từ ảnh chụp và **Knowledge Graph** để truy xuất dữ liệu y khoa, từ đó đưa ra lời khuyên chính xác xem người bệnh có nên ăn hay không.

## 🚀 Tính năng nổi bật

* **📸 AI Vision (Thị giác máy tính):**
    * Nhận diện món ăn qua Camera trực tiếp hoặc ảnh tải lên.
    * Phân tích thành phần nguyên liệu và ước lượng dinh dưỡng.
* **🧠 Knowledge Graph (Đồ thị tri thức):**
    * Lưu trữ hàng ngàn mối quan hệ giữa Bệnh lý - Thực phẩm - Chất dinh dưỡng trong Neo4j.
    * Truy vấn cực nhanh các món "Đại kỵ" hoặc "Nên dùng".
* **💬 Tư vấn Y khoa Thông minh:**
    * Kết hợp dữ liệu Graph và mô hình ngôn ngữ lớn (LLM) để giải thích lý do tại sao nên/không nên ăn.
* **✨ Giao diện Hiện đại:**
    * Thiết kế Glassmorphism (Kính mờ).
    * Responsive 100% (Tương thích máy tính & điện thoại).
    * Hiệu ứng chuyển động mượt mà.

## 🛠️ Công nghệ sử dụng

| Phân hệ | Công nghệ | Chi tiết |
| :--- | :--- | :--- |
| **Frontend** | ReactJS (Vite) | Xây dựng giao diện người dùng tốc độ cao. |
| | AnimeJS | Thư viện hiệu ứng chuyển động (Animation). |
| | Nginx | Web Server & Reverse Proxy (Cổng giao tiếp). |
| **Backend** | Python (FastAPI) | Xây dựng API Server hiệu năng cao. |
| | Docker | Đóng gói và triển khai ứng dụng (Containerization). |
| **Database** | Neo4j | Cơ sở dữ liệu đồ thị (Graph Database). |
| **AI Core** | Llama 3.2 Vision / GPT-OSS | Mô hình AI nhận diện ảnh và lập luận y khoa (thông qua Groq Cloud). |

## 📂 Cấu trúc thư mục

Dự án được tổ chức theo cấu trúc Microservices chuẩn:

```text
MyProject/
├── 📂 backend/                 # Mã nguồn Backend (Python/FastAPI)
│   ├── 📂 app/                 # Logic chính (AI, Graph, API)
│   ├── Dockerfile              # Cấu hình Docker Backend
│   └── requirements.txt        # Thư viện Python
├── 📂 frontend-diet/           # Mã nguồn Frontend (ReactJS)
│   ├── 📂 src/                 # Code giao diện (App.jsx, App.css)
│   ├── Dockerfile              # Cấu hình Docker Frontend (Node 22)
│   └── .dockerignore           # Loại bỏ file rác khi build
├── 📂 nginx/                   # Cấu hình Gateway
│   └── default.conf            # File điều hướng port 80
├── 📂 thesis/                  # Tài liệu báo cáo đồ án
│   ├── Bao_Cao.docx
│   └── Slide.pptx
├── 📂 neo4j_data/              # Dữ liệu bền vững của Database
├── docker-compose.yml          # File điều phối toàn bộ hệ thống
└── README.md                   # Tài liệu hướng dẫn (File này)