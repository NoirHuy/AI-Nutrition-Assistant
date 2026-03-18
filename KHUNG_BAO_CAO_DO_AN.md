# MẪU BÁO CÁO ĐỒ ÁN: XÂY DỰNG ĐỒ THỊ TRI THỨC VỀ DINH DƯỠNG THEO BỆNH LÝ CÁ NHÂN

## CHƯƠNG I: GIỚI THIỆU
### 1.1 Lý do chọn đề tài
- **Bối cảnh:** Dinh dưỡng đóng vai trò cốt lõi trong việc phòng ngừa và điều trị các bệnh mãn tính (tiểu đường, tim mạch, gout, suy thận). Tuy nhiên, đối với người mắc **nhiều bệnh lý nền cùng lúc (bệnh lý chồng chéo)**, việc thiết kế khẩu phần ăn thường gặp mâu thuẫn khắt khe (ví dụ: món ăn này tốt cho bệnh A nhưng lại cấm chỉ định cho bệnh B).
- **Vấn đề hiện tại:** Các ứng dụng tra cứu y tế hiện nay hoạt động dựa trên luật (rule-based) hoặc cơ sở dữ liệu quan hệ (SQL) cứng nhắc. Chúng không có khả năng liên kết hay phân tích sự chằng chịt của mạng lưới dinh dưỡng, cũng như thiếu tính tự động cập nhật tri thức y khoa mới.
- **Giải pháp đề xuất:** Ứng dụng Đồ thị tri thức (Knowledge Graph - KG) kết hợp các Mô hình ngôn ngữ lớn (LLM) để tự động hóa thu thập kiến thức, biểu diễn các mối quan hệ dinh dưỡng đa chiều. Từ đó, mang đến hệ thống tư vấn thông minh, chính xác, xử lý triệt để bài toán mâu thuẫn bệnh lý cá nhân. Đề tài **“Xây dựng đồ thị tri thức về dinh dưỡng theo bệnh lý cá nhân”** được ra đời từ nhu cầu cấp thiết đó.

### 1.2 Sơ lược về chương trình
Hệ thống là một giải pháp hoàn chỉnh với 2 lõi kiến trúc chính:
- **Khối Xây dựng tri thức (Knowledge Construction Offline):** Áp dụng framework luồng dữ liệu EDC (Extract - Define - Canonicalize). Hệ thống sử dụng trí tuệ nhân tạo (LLM Llama-3.3-70B và Jina Embeddings) đọc hiểu tự động các bảng thành phần thực phẩm và tài liệu y khoa thô, rồi trích xuất thành các "Bộ ba tri thức" (Subject - Relation - Object).
- **Khối Lưu trữ và Tư vấn (Service Online):** 
  - Toàn bộ tri thức được đổ vào cơ sở dữ liệu đồ thị Neo4j.
  - Xây dựng Web App tương tác với người dùng thông qua API (Python/FastAPI). Hệ thống áp dụng công nghệ GraphRAG (áp dụng LLM đọc thông tin đồ thị) để tra cứu thực đơn, phát hiện chống chỉ định và trả về cảnh báo tư vấn cá nhân hóa tới người bệnh.

### 1.3 Ý nghĩa của đề tài
- **Về mặt công nghệ:** Tiên phong áp dụng các luồng công nghệ phân tích SOTA (State OF The Art) của năm 2024-2025: Xử lý thông tự do (OIE), Graph Database (Neo4j), và GraphRAG. Thể hiện sự dịch chuyển khỏi CSDL quan hệ truyền thống kém hiệu quả.
- **Về mặt thực tiễn - y tế:** Cung cấp công cụ mạnh mẽ hỗ trợ cho bác sĩ dinh dưỡng. Trở thành "trợ lý sức khỏe ảo" bảo vệ người bệnh (đặc biệt là người cao tuổi) khỏi các rủi ro biến chứng do thiếu hiểu biết về tương tác thực phẩm.

---

## CHƯƠNG II: CƠ SỞ LÝ LUẬN VÀ PHƯƠNG PHÁP NGHIÊN CỨU
### 2.1 Phân tích yêu cầu
#### 2.1.1 Xác định yêu cầu
- **Yêu cầu chức năng:** Hệ thống có khả năng crawl/đọc văn bản thô; tự động trích xuất các đỉnh thông tin (Thực phẩm, Dưỡng chất, Bệnh) và các cung độ tương tác (Chứa, Giàu, Làm trầm trọng, Chống chỉ định...); chức năng tư vấn cảnh báo khi người dùng nhập thông tin hồ sơ bệnh án.
- **Yêu cầu phi chức năng:** Phải xử lý được sự cố Rate limit khi gọi API LLM; tốc độ truy vấn Cypher trong Neo4j phải cực mượt (dưới 1 giây); tính chính xác y khoa phải được kiểm soát tuyệt đối (giảm thiểu ảo giác (Hallucination) của AI).

#### 2.1.2 Thu thập yêu cầu
- Nguồn tài liệu y khoa tiếng Anh (Tiểu đường, HERD, v.v.).
- Bảng Excel thành phần dinh dưỡng thực phẩm bản địa Việt Nam.

#### 2.1.3 Phân tích quy trình kinh doanh (Nghiệp vụ)
- **Quy trình Quản trị (Knowledge ETL):** Văn bản thô $\rightarrow$ Tiền xử lý $\rightarrow$ Gọi LLM trích xuất thô $\rightarrow$ Gọi Embedding chuẩn hoá theo Từ điển Ontology $\rightarrow$ Lưu vào Neo4j.
- **Quy trình Xử lý yêu cầu tư vấn:** Người dùng khai báo Profile $\rightarrow$ Hệ thống gọi Cypher chọc vào Graph $\rightarrow$ Quét mạng lưới kết nối xem thực phẩm xung đột với Profile người dùng không $\rightarrow$ Tổng hợp trả lời lên frontend.

### 2.2 Mô hình hệ thống và thiết kế
#### 2.2.1 Mô hình hệ thống
- Kiến trúc Service-Oriented Architecture (SOA), phân tách rõ tầng Pipeline trích xuất (Background Task), tầng lưu trữ (Graph Database), và tầng Dịch vụ tương tác AI.

#### 2.2.2 Thiết kế cơ sở dữ liệu
- Chuyển đổi mô hình dữ liệu quan hệ (Relational Model) sang **Mô hình Dữ liệu Đồ thị thuộc tính (Property Graph Model)**. Tập trung phân bổ thiết kế Cạnh Graph thay vì thiết kế Bảng (Tables).

#### 2.2.3 Giao diện người dùng
- Một Web App hiển thị với khung chat (Agent interaction) và giao diện minh họa mạng lưới trực quan.

### 2.3 Phát triển phần mềm
#### 2.3.1 Lựa chọn công nghệ
- **Data Engineering / Trích xuất (Extract):** Python (Regex, Openpyxl, SentenceTransformers).
- **AI Core:** Mô hình Llama-3.3 qua Groq API (giải quyết LLM logic), Jina Embeddings (so khớp Cosine Similarity). 
- **Database:** Neo4j (ngôn ngữ truy vấn Cypher).
- **Backend / API:** Python web framework (Flask/FastAPI).
- **Môi trường chạy:** Docker và Antigravity Workspace.

#### 2.3.2 Kiểm thử đơn vị và tích hợp
- Đánh giá chéo chất lượng bộ ba tri thức do AI trích xuất với File nhãn gốc do con người thiết lập. Kiểm tra lỗi mất mát dữ liệu khi gộp file dữ liệu phân mảnh (Map/Reduce logic).

### 2.4 Triển khai và duy trì
- Cấu hình file Docker-compose triển khai mượt mà Image Neo4j `neo4j:5.16`.
- Quy trình human-in-the-loop (chuyên gia y tế tham gia) khi cập nhật thêm tri thức mới nằm ngoài schema cứng (`--enrich_schema`).

### 2.5 Phương pháp nghiên cứu
- Nghiên cứu cơ sở lý thuyết Xử lý ngôn ngữ tự nhiên (OIE - Open Information Extraction).
- Áp dụng phương pháp luận Extract-Define-Canonicalize (EDC) nhằm kiểm soát nhiễu của LLM.
- Phương pháp thực nghiệm: Xây dựng pipeline, nạp dữ liệu thật và chạy thử Graph Agent để xem độ chính xác.

---

## CHƯƠNG III: GIỚI THIỆU TỔNG QUAN VỀ VẤN ĐỀ NGHIÊN CỨU
### 3.1 Tổng quan về vấn đề nghiên cứu
#### 3.1.1 Khái niệm cơ bản
- Trình bày định nghĩa Đồ thị tri thức (Knowledge Graph), Nút (Nodes) & Cạnh (Edges).
- Kiến trúc Semantic Web và các chuẩn Ontology.

#### 3.1.2 Mục tiêu của hệ thống Tư vấn Dinh dưỡng cá nhân hóa
- Chuyển đổi thành công bộ từ vựng phi cấu trúc y khoa thành một bộ CSDL mạng lưới tường minh, liên kết chặt chẽ.
- Cung cấp tính năng truy vấn mâu thuẫn dinh dưỡng theo thời gian thực (real-time recommendation insight).

#### 3.1.3 Phạm vi ứng dụng
- Hệ thống cover 5-6 bệnh lý lớn: Tiểu đường, Cao huyết áp, Gout, Béo phì, Suy thận, Trào ngược dạ dày; cùng hơn 160 loại thực phẩm Việt Nam.

#### 3.1.4 Khả năng phát triển
- Tích hợp thêm Wearable device để lấy chỉ số sinh tồn. Mở rộng kho tàng lên mức quy mô bách khoa toàn thư món ăn, gợi ý thực đơn (Meal Planner) linh động dùng Constraints Programming.

#### 3.1.5 Các yêu cầu
- Yêu cầu tiên quyết: LLM trong hệ thống đóng vai trò biên dịch (Translator), chứ không phải người sáng tác. Mọi câu trả lời của AI phải bám rễ vào tập tri thức Graph đã được khai phá nhằm triệt tiêu "ảo giác" (Hallucination).

### 3.2 Khảo sát hiện trạng
- Nêu rõ nhược điểm của việc áp dụng cơ sở dữ liệu SQL cứng khi có những loại đồ ăn gây ra ảnh hưởng gián tiếp qua nhiều bước. 
- Chỉ ra rủi ro y tế trên thực trạng các phần mềm AI (như ChatGPT) trả lời tư vấn một cách ngẫu nhiên mà không dựa trên cơ sở quy chuẩn tri thức vững chắc.

---

## CHƯƠNG IV: PHÂN TÍCH VÀ THIẾT KẾ UML
*(Trong hệ thống phần mềm trí tuệ nhân tạo, một số sơ đồ sẽ được tinh chỉnh lại)*

### 4.1 Mô hình phân rã chức năng BFD (Business Function Diagram)
- Phân rã thành: (1) Khối Quản trị/Developer thao tác với Core ETL. (2) Khối End-user giao tiếp lấy Query tư vấn.

### 4.2 Lược đồ Đồ thị Dữ liệu - Graph Data Model (Thay cho ERD)
- *Lưu ý: Báo cáo của bạn làm Neo4j, nên ERD (Entity Relationship Diagram - dành cho SQL) phải được đổi tên thành **Graph Data Model** hay Lược đồ Neo4j Property.*
- Vẽ hình khối vòng tròn (Nodes) và các mũi tên chỉ hướng (Relationships). 
- Các Node chính: `(FoodVN)`, `(Disease)`, `(Nutritional Component)`.

### 4.3 Mô hình luồng dữ liệu DFD (Data Flow Diagram)
- Mức 0: Toàn bộ quá trình từ thu thập Input tài liệu Excel/Text vứt vào hệ thống, sau đó in ra Neo4j Browser.
- Mức 1: Bóc tách Phase 1 (LLM OIE Extraction), Phase 2 (LLM Schema Definition), Phase 3 (Jina Vector Canonicalization) như đã phân tích thiết kế ở quyển 1.

### 4.4 Sơ Đồ Lớp (Class Diagram)
- Mô tả class thiết kế lõi: Class `EDC`, `Extractor`, `SchemaDefiner`, `SchemaCanonicalizer`, và cách chúng gọi Utils (LLM_API).

---

## CHƯƠNG V: THIẾT KẾ CƠ SỞ DỮ LIỆU
*(Chương này tùy biến cho Database Đồ thị)*

### 5.1 Các Đỉnh thực thể (Nodes)
*(Liệt kê các dải dữ liệu được đổ làm đỉnh đồ thị)*
- Mẫu Node thực phẩm: Tên (Gạo nếp cái), Nhãn (FoodVN), Năng lượng (kcal)...
- Mẫu Node Bệnh lý: Tên bệnh.

### 5.2 Các cung Quan hệ và Nhãn (Relationships / Edges)
- Hệ thống hỗ trợ bộ Schema chuẩn 12 Lệnh Tương Tác cho tiếng Việt.
- Ví dụ cạnh: `[CHỨA]`, `[GIÀU]`, `[CẦN_HẠN_CHẾ_Ở]`, `[ẢNH_HƯỞNG_ĐƯỜNG_HUYẾT]`, `[CHỐNG_CHỈ_ĐỊNH_VỚI]`.
- Nêu rõ thuộc tính mũi tên: Thuộc tính này có mang theo weight (Trọng số ảnh hưởng) hay không.

### 5.3 Sơ Đồ Use Case
- Vẽ diễn giải kịch bản tổng quan: Use Case Trích xuất tự động qua chia Part, Use Case Chuẩn hóa trùng lặp (Dedup), Use Case Truy vấn Cypher lấy dữ liệu cảnh báo từ giao diện Frontend.
