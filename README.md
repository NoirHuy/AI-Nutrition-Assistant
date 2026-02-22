# CHƯƠNG 1: NGHIÊN CỨU TỔNG QUAN VỀ DỰ ÁN

## 1.1. Giới Thiệu Vấn Đề

Trong bối cảnh y học cá nhân hóa (personalized medicine) ngày càng phát triển, nhu cầu xây dựng các hệ thống tư vấn dinh dưỡng dựa trên hồ sơ bệnh lý cụ thể của từng cá nhân trở nên cấp thiết hơn bao giờ hết. Các rối loạn chuyển hóa như tiểu đường type 2, tăng huyết áp, bệnh thận mãn tính, hay các bệnh lý liên quan đến dinh dưỡng như thiếu máu thiếu sắt, loãng xương đều đòi hỏi chế độ dinh dưỡng đặc thù và được khuyến nghị bởi các hướng dẫn lâm sàng quốc tế.

Tuy nhiên, tri thức dinh dưỡng-bệnh lý hiện nay tồn tại dưới dạng văn bản phi cấu trúc (unstructured text) trong các bài báo khoa học, chỉ dẫn lâm sàng và sách giáo khoa y khoa, gây khó khăn cho việc tích hợp vào các hệ thống hỗ trợ ra quyết định (Clinical Decision Support Systems). **Đồ thị tri thức (Knowledge Graph — KG)** là một phương pháp biểu diễn tri thức có cấu trúc hiệu quả, cho phép lưu trữ và truy vấn các mối quan hệ phức tạp giữa thực thể (entity) như thực phẩm, dưỡng chất và bệnh lý.

**Mục tiêu của dự án** là xây dựng một đồ thị tri thức dinh dưỡng theo bệnh lý cá nhân bằng cách tự động trích xuất tri thức từ các tài liệu y khoa sử dụng các mô hình ngôn ngữ lớn (Large Language Models — LLMs), cụ thể thông qua framework **EDC (Extract–Define–Canonicalize)**.

---

## 1.2. Các Khái Niệm Cơ Bản

### 1.2.1. Đồ Thị Tri Thức (Knowledge Graph)

Đồ thị tri thức là một cơ sở tri thức biểu diễn thông tin dưới dạng các bộ ba: **(Subject, Relation, Object)**, còn gọi là **bộ ba RDF (Resource Description Framework)**. Ví dụ:

```
(Vitamin D, phòng ngừa, Loãng xương)
(Natri, làm trầm trọng, Tăng huyết áp)
(Sắt, nguồn thực phẩm, Thịt đỏ)
```

Các đồ thị tri thức nổi tiếng như **Wikidata**, **DBpedia**, và **UMLS** (Unified Medical Language System) đã được ứng dụng rộng rãi trong y sinh học. Tuy nhiên, việc xây dựng KG cho domain dinh dưỡng-bệnh lý chuyên biệt vẫn còn rất hạn chế.

### 1.2.2. Mô Hình Ngôn Ngữ Lớn (LLM)

Các mô hình ngôn ngữ lớn như **Llama-3**, **GPT-4**, **Mistral** đã đạt được khả năng hiểu và sinh văn bản gần như người thật. Trong bối cảnh Information Extraction (IE), LLM có thể được sử dụng để:

- Trích xuất bộ ba quan hệ từ văn bản phi cấu trúc (**OIE — Open Information Extraction**)
- Định nghĩa ngữ nghĩa của các quan hệ (**Schema Definition**)
- Ánh xạ qua schema chuẩn (**Schema Canonicalization**)

### 1.2.3. Embedding và Tương Đồng Ngữ Nghĩa

**Embedding** là quá trình chuyển đổi văn bản thành vector số trong không gian đa chiều. Các vector gần nhau trong không gian này có nghĩa ngữ nghĩa tương đồng. Trong dự án này, **Jina Embeddings v3** được sử dụng để tính toán độ tương đồng ngữ nghĩa giữa các quan hệ trích xuất được và các quan hệ trong schema chuẩn.

---

## 1.3. Tổng Quan Các Công Trình Liên Quan

### 1.3.1. Hướng Tiếp Cận Truyền Thống

Trước khi LLM phổ biến, việc xây dựng KG từ văn bản y sinh học dựa chủ yếu vào:

| Phương pháp | Hạn chế |
|-------------|---------|
| **Rule-based NLP** (Regular Expression, POS Tagging) | Cần nhiều công sức viết rules; không tổng quát hóa tốt |
| **Supervised ML** (SVM, BiLSTM) | Cần dữ liệu annotated lớn; tốn chi phí gán nhãn |
| **OpenIE truyền thống** (Stanford OpenIE, ReVerb) | Trích xuất quan hệ thô, thiếu ngữ nghĩa; không theo schema |

### 1.3.2. Hướng Tiếp Cận Dựa Trên LLM

Các nghiên cứu gần đây cho thấy LLM có thể thực hiện IE chất lượng cao với **zero-shot hoặc few-shot prompting**, không cần dữ liệu annotated:

- **GPT-NER** (Wang et al., 2023): Sử dụng ChatGPT để nhận dạng thực thể y sinh học
- **PubMedBERT + Relation Extraction**: Fine-tune BERT trên dữ liệu y sinh học cho phân loại quan hệ
- **ChatIE** (Wei et al., 2023): Chuyển đổi IE thành bài toán hội thoại với LLM

### 1.3.3. EDC Framework

**EDC (Extract–Define–Canonicalize)** được giới thiệu bởi Guo et al. (2023) là framework xây dựng KG theo hướng **schema-guided** — tức là có một schema quan hệ đích định sẵn. EDC giải quyết thách thức quan trọng: làm thế nào để ánh xạ các quan hệ trích xuất tự do sang schema chuẩn một cách ngữ nghĩa chính xác.

---

## 1.4. Kiến Trúc Hệ Thống EDC

Framework EDC hoạt động theo pipeline 3 pha tuần tự:

```
┌──────────────────────────────────────────────────────────────────┐
│                      VĂN BẢN Y KHOA ĐẦU VÀO                     │
│  "Bệnh nhân tiểu đường type 2 nên hạn chế carbohydrate tinh luyện"│
└──────────────────────────────┬───────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   PHASE 1: OIE      │ ← LLM (Groq: llama-3.3-70b)
                    │ Open Info Extract   │
                    │                     │
                    │  Subject  Rel  Obj  │
                    │ (refined_carbs) →   │
                    │  aggravates →       │
                    │ (type2_diabetes)    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   PHASE 2: SD       │ ← LLM (Groq: llama-3.3-70b)
                    │ Schema Definition   │
                    │                     │
                    │ "aggravates":       │
                    │  Subject làm trầm   │
                    │  trọng thêm Object  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   PHASE 3: SC       │ ← Embedder: Jina v3
                    │ Schema Canonical.   │   + LLM verify (Groq)
                    │                     │
                    │ "aggravates" →      │
                    │   map to schema →   │
                    │   "aggravates"      │
                    └──────────┬──────────┘
                               │
               ┌───────────────▼────────────────┐
               │   KNOWLEDGE GRAPH ĐẦU RA       │
               │ (refined_carbs, aggravates,     │
               │   type_2_diabetes)              │
               └────────────────────────────────┘
```

### Phase 1 — OIE (Open Information Extraction)
LLM được cung cấp văn bản đầu vào và các few-shot examples, sau đó sinh ra danh sách bộ ba `(Subject, Relation, Object)` dạng thô. Không bị ràng buộc bởi schema — cho phép phát hiện mọi quan hệ có trong văn bản.

### Phase 2 — SD (Schema Definition)
LLM định nghĩa ngữ nghĩa chính xác cho từng quan hệ đã trích xuất dựa trên ngữ cảnh văn bản gốc, giúp phân biệt các quan hệ có từ giống nhau nhưng nghĩa khác.

### Phase 3 — SC (Schema Canonicalization)
1. **Embedding Search**: Jina Embeddings v3 tính độ tương đồng cosine giữa định nghĩa của quan hệ trích xuất và tất cả quan hệ trong schema đích → lấy top-K candidates
2. **LLM Verify**: LLM kiểm tra và quyết định ánh xạ cuối cùng (hoặc loại bỏ nếu không phù hợp)

---

## 1.5. Cơ Sở Hạ Tầng Kỹ Thuật

### 1.5.1. Mô Hình Ngôn Ngữ — Groq API

| Thông tin | Chi tiết |
|-----------|---------|
| **Nhà cung cấp** | Groq Cloud |
| **Mô hình sử dụng** | `llama-3.3-70b-versatile` |
| **Tham số** | 70 tỷ (70B parameters) |
| **Đặc điểm** | Tốc độ inference cực nhanh (LPU hardware), tốc độ ~800 tokens/giây |
| **Lý do chọn** | Miễn phí (rate-limited), không yêu cầu GPU cục bộ |

### 1.5.2. Mô Hình Embedding — Jina AI API

| Thông tin | Chi tiết |
|-----------|---------|
| **Nhà cung cấp** | Jina AI |
| **Mô hình sử dụng** | `jina-embeddings-v3` |
| **Chiều vector** | 1024 chiều |
| **Đặc điểm** | Hỗ trợ prompts cho domain cụ thể, state-of-the-art trên MTEB |
| **Lý do chọn** | API miễn phí (1M tokens), không cần tải model local |

### 1.5.3. Yêu Cầu Phần Cứng Sau Tối Ưu

| Thành phần | Yêu cầu |
|-----------|---------|
| **GPU/VRAM** | Không yêu cầu (100% API) |
| **RAM** | ≥ 8 GB |
| **CPU** | Bất kỳ (Intel/AMD) |
| **Kết nối mạng** | Bắt buộc (gọi API) |
| **Python** | 3.11+ |

---

## 1.6. Schema Quan Hệ Dinh Dưỡng-Bệnh Lý

Dự án định nghĩa **15 loại quan hệ** để biểu diễn tri thức dinh dưỡng theo bệnh lý:

| Quan hệ | Ý nghĩa |
|---------|---------|
| `treats` | Chất dinh dưỡng/thực phẩm dùng để điều trị bệnh |
| `prevents` | Chất dinh dưỡng/thực phẩm giúp phòng ngừa bệnh |
| `aggravates` | Thực phẩm/chất làm trầm trọng thêm bệnh lý |
| `recommended_for` | Được khuyến nghị cho bệnh nhân mắc bệnh cụ thể |
| `contraindicated_for` | Chống chỉ định với bệnh nhân mắc bệnh cụ thể |
| `deficiency_causes` | Thiếu hụt dưỡng chất gây ra bệnh |
| `enhances_absorption_of` | Tăng cường hấp thu dưỡng chất khác |
| `restricts` | Bệnh nhân mắc bệnh cần hạn chế chất này |
| `requires` | Bệnh nhân mắc bệnh cần bổ sung chất này |
| `contains` | Thực phẩm chứa dưỡng chất |
| `reduces` | Giảm mức độ/triệu chứng bệnh |
| `associated_with` | Liên quan đến nguy cơ bệnh (tương quan) |
| `daily_intake` | Liều lượng khuyến nghị hàng ngày |
| `food_source` | Nguồn thực phẩm cung cấp dưỡng chất |
| `symptom_of` | Biểu hiện lâm sàng của bệnh |

---

## 1.7. Ứng Dụng Thực Tiễn

Đồ thị tri thức dinh dưỡng-bệnh lý được xây dựng có thể làm nền tảng cho:

1. **Hệ thống tư vấn dinh dưỡng cá nhân hóa**: Truy vấn "Bệnh nhân tiểu đường type 2 nên ăn gì?" → Graph traversal → Danh sách thực phẩm được khuyến nghị
2. **Hệ thống cảnh báo tương tác dinh dưỡng-thuốc**: Phát hiện các thực phẩm chống chỉ định khi dùng thuốc
3. **Hỗ trợ lập kế hoạch thực đơn bệnh viện**: Tự động hóa quy trình dietitian
4. **Nền tảng giáo dục dinh dưỡng**: Trực quan hóa mối quan hệ dinh dưỡng-bệnh lý

---

## 1.8. Kết Luận Chương

Dự án "Xây dựng đồ thị tri thức dinh dưỡng theo bệnh lý cá nhân" áp dụng framework **EDC** kết hợp với API của **Groq** (Llama-3.3-70B) và **Jina AI** để tự động hóa quá trình trích xuất và cấu trúc hóa tri thức y khoa từ văn bản phi cấu trúc. Hướng tiếp cận này vượt qua các hạn chế về phần cứng của phương pháp dùng mô hình cục bộ, đồng thời tận dụng khả năng suy luận vượt trội của các LLM quy mô lớn để đảm bảo chất lượng trích xuất tri thức.

Framework đã được kiểm chứng chạy thành công trên 10 đoạn văn y khoa bao gồm các bệnh lý: tiểu đường, tăng huyết áp, bệnh thận mãn tính, thiếu máu, bệnh celiac, gout, loãng xương, gan nhiễm mỡ, bệnh tuyến giáp và phenylceton niệu, tạo ra đồ thị tri thức dinh dưỡng có cấu trúc với 15 loại quan hệ chuẩn hóa.
