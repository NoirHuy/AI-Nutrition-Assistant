# PHÂN TÍCH HỆ THỐNG: PIPELINE TRÍCH XUẤT KNOWLEDGE GRAPH

> **Đồ Án 2 — Hệ Thống Tư Vấn Dinh Dưỡng Thông Minh**
> Tài liệu: Phân tích thiết kế module xây dựng Đồ Thị Tri Thức (KG)

---

## 1. TỔNG QUAN MODULE

### 1.1. Mục tiêu

Module trích xuất Knowledge Graph (KG) chịu trách nhiệm **tự động chuyển đổi dữ liệu văn bản phi cấu trúc** (tài liệu y khoa tiếng Anh, bảng dinh dưỡng thực phẩm tiếng Việt) thành **đồ thị tri thức có cấu trúc** lưu trong Neo4j, phục vụ cho hệ thống tư vấn dinh dưỡng theo bệnh lý.

### 1.2. Hai luồng dữ liệu song song

| Luồng | Nguồn dữ liệu | Schema | Label Neo4j |
|-------|--------------|--------|-------------|
| **Luồng 1** | Tài liệu y khoa tiếng Anh (`diabetes_en.txt`, GERD, v.v.) | `nutrition_schema.csv` (15 quan hệ) | `TieuDuongKG` |
| **Luồng 2** | Excel thực phẩm Việt Nam (`food_vietnam_final.xlsx`) | `food_nutrition_schema.csv` (12 quan hệ) | `FoodVN` |

### 1.3. Framework sử dụng: EDC

Pipeline sử dụng framework **EDC (Extract–Define–Canonicalize)** với 3 pha xử lý nối tiếp nhau:

```
Văn bản đầu vào
       ↓
  [Phase 1: OIE]   → Trích xuất bộ ba thô (Subject, Relation, Object)
       ↓
  [Phase 2: SD]    → Định nghĩa ngữ nghĩa từng quan hệ
       ↓
  [Phase 3: SC]    → Ánh xạ quan hệ về schema chuẩn (Canonicalization)
       ↓
  canon_kg.txt     → Tập triple đã được chuẩn hoá
```

---

## 2. SƠ ĐỒ USE CASE

```mermaid
flowchart LR
    Dev["👨‍💻 Nhà phát triển\n(Data Engineer)"]

    subgraph SYS["Hệ thống trích xuất KG"]
        direction TB

        subgraph PRE["Chuẩn bị dữ liệu"]
            UC1a["Chuyển Excel → TXT\n(excel_to_txt.py)"]
            UC1b["Tiền xử lý văn bản\n(preprocess_document_en.py)"]
            UC1c["Chia file thành N parts\n(split_and_merge.py split)"]
        end

        subgraph EXTRACT["Trích xuất KG — EDC Pipeline"]
            UC2["Chạy pipeline EDC\n(run.py)"]
            subgraph EDC_inner["Ba pha xử lý"]
                P1["Phase 1: OIE\nOpen Information Extraction"]
                P2["Phase 2: SD\nSchema Definition"]
                P3["Phase 3: SC\nSchema Canonicalization"]
                P1 --> P2 --> P3
            end
            UC2 --> EDC_inner
        end

        subgraph POST["Hậu xử lý & Lưu trữ"]
            UC3["Gộp kết quả các part\n(split_and_merge.py merge)"]
            UC4["Khử trùng lặp\n(exact dedup theo tuple)"]
            UC5["Import vào Neo4j\n(import_to_neo4j.py)"]
            UC3 --> UC4 --> UC5
        end

        subgraph VERIFY["Kiểm chứng"]
            UC6["Truy vấn KG\n(Neo4j Browser / Cypher)"]
            UC7["Kiểm tra API tư vấn\n(curl /api/chat)"]
        end
    end

    Groq["☁️ Groq API\n(Llama-3.3-70B)"]
    Jina["☁️ Jina AI API\n(jina-embeddings-v3)"]
    Neo4j["🗄️ Neo4j 5.16\n(bolt://localhost:7687)"]

    Dev --> PRE
    Dev --> UC2
    Dev --> POST
    Dev --> VERIFY

    P1 -. "Chat Completion" .-> Groq
    P2 -. "Chat Completion" .-> Groq
    P3 -. "Embedding" .-> Jina
    P3 -. "LLM verify" .-> Groq
    UC5 -. "Bolt protocol" .-> Neo4j
    UC6 -. "HTTP Browser" .-> Neo4j
```

---

## 3. SƠ ĐỒ SEQUENCE — LUỒNG XỬ LÝ ĐẦY ĐỦ

### 3.1. Luồng 2: Dữ liệu thực phẩm Việt Nam (Food KG)

```mermaid
sequenceDiagram
    actor Dev as Nhà phát triển
    participant Excel as food_vietnam_final.xlsx
    participant Prep as excel_to_txt.py
    participant Split as split_and_merge.py
    participant Run as run.py (EDC)
    participant OIE as Extractor (OIE)
    participant SD as SchemaDefiner (SD)
    participant SC as SchemaCanonicalization (SC)
    participant Groq as Groq API
    participant Jina as Jina Embeddings API
    participant Merge as split_and_merge.py merge
    participant Import as import_to_neo4j.py
    participant DB as Neo4j Database

    Note over Dev,DB: BƯỚC 1 — Chuẩn bị dữ liệu
    Dev->>Prep: python excel_to_txt.py
    Prep->>Excel: openpyxl.load_workbook()
    Excel-->>Prep: 162 hàng dữ liệu thực phẩm
    Prep->>Prep: food_to_paragraph(row)<br/>→ Tạo mô tả tự nhiên tiếng Việt
    Prep-->>Dev: datasets/food_vietnam.txt (162 dòng)

    Dev->>Split: python split_and_merge.py split --parts 10
    Split->>Split: Chia thành 10 file<br/>~16 dòng / file
    Split-->>Dev: food_vietnam_part01..10.txt<br/>+ In 10 lệnh run.py

    Note over Dev,DB: BƯỚC 2 — EDC Pipeline (lặp cho mỗi part)
    loop Với mỗi part_i (i = 01..10)
        Dev->>Run: python run.py --input part_i.txt<br/>--sc_embedder jina-embeddings-v3

        loop Với mỗi dòng văn bản trong part_i
            Run->>OIE: extract(text, oie_few_shot, template)
            OIE->>Groq: POST /v1/chat/completions<br/>model=llama-3.3-70b-versatile<br/>prompt=[system+few_shot+text]
            alt Rate limit (10,000 TPM)
                Groq-->>OIE: 429 + "try again in 10m4.8s"
                OIE->>OIE: parse wait_time từ error<br/>sleep(wait_total + 5s buffer)
                OIE->>Groq: Retry
            end
            Groq-->>OIE: [["S","R","O"], ...]
            OIE-->>Run: oie_triples[]

            Run->>SD: define(oie_triples, few_shot)
            SD->>Groq: Chat Completion (SD prompt)
            Groq-->>SD: {"relation": "chứa", "definition": "..."}
            SD-->>Run: relation_definitions[]

            Run->>SC: canonicalize(triples, definitions, schema)
            SC->>Jina: POST /v1/embeddings<br/>["chứa", "giàu", "thuộc nhóm", ...]
            Jina-->>SC: embedding_vectors[]
            SC->>SC: cosine_similarity(relation_vec, schema_vecs)<br/>→ Chọn quan hệ chuẩn gần nhất
            opt Nếu similarity thấp (< threshold)
                SC->>Groq: Chat Completion (SC verify prompt)
                Groq-->>SC: "yes" / "no"
            end
            SC-->>Run: canon_triples[]
        end

        Run-->>Dev: output/part_i/iter0/canon_kg.txt<br/>(mỗi dòng = list triple của 1 đoạn văn)
    end

    Note over Dev,DB: BƯỚC 3 — Hậu xử lý
    Dev->>Merge: python split_and_merge.py merge --parts 10
    loop Với mỗi part_i
        Merge->>Merge: ast.literal_eval(dòng)<br/>→ Flatten list of lists → list triple
    end
    Merge->>Merge: Exact dedup: set(tuple(s,r,o))<br/>Loại bỏ triple trùng
    Merge-->>Dev: output/kg_flat.txt<br/>(N triples duy nhất, mỗi dòng = ['s','r','o'])

    Note over Dev,DB: BƯỚC 4 — Import vào Neo4j
    Dev->>Import: python import_to_neo4j.py<br/>--kg_file kg_flat.txt<br/>--label FoodVN
    Import->>Import: ast.literal_eval(line)<br/>→ [subject, relation, object]
    Import->>Import: relation_to_cypher_type(r)<br/>→ "CHỨA", "GIÀU", v.v.
    Import->>DB: CREATE CONSTRAINT entity_name IF NOT EXISTS
    loop Với mỗi triple (s, r, o)
        Import->>DB: MERGE (a:FoodVN {name:s})<br/>MERGE (b:FoodVN {name:o})<br/>MERGE (a)-[:REL {relation:r}]->(b)
    end
    DB-->>Import: success_count, failed_count
    Import-->>Dev: ✅ Imported N triples | Failed: 0
```

---

## 4. SƠ ĐỒ CLASS — EDC FRAMEWORK

```mermaid
classDiagram
    direction TB

    class EDC {
        +oie_llm : str
        +sd_llm : str
        +sc_llm : str
        +sc_embedder_name : str
        +target_schema_path : str
        +refinement_iterations : int
        +enrich_schema : bool
        -loaded_model_dict : dict
        -target_schema : dict
        
        +__init__(oie_llm, sd_llm, sc_llm, sc_embedder, target_schema_path, ...)
        +extract_kg(input_text_list, output_dir, refinement_iterations) list
        +oie(input_texts) tuple
        +schema_definition(oie_triplets, entity_hints, relation_hints) list
        +schema_canonicalization(oie_triplets, sd_results) tuple
        +load_model(model_name, model_type) object
        -_save_results(output_dir, stage, data)
        -_load_schema(schema_path) dict
    }

    class Extractor {
        +openai_model : str
        +prompt_template_str : str
        +few_shot_examples_str : str
        
        +extract(input_text, few_shot_examples, prompt_template) list~list~
        -_parse_response(response_text) list
    }

    class SchemaDefiner {
        +openai_model : str
        +prompt_template_str : str
        +few_shot_examples_str : str
        
        +define(triplets, entity_hints, relation_hints, few_shot, template) list~dict~
        -_parse_definitions(response) dict
    }

    class SchemaCanonicalization {
        +llm_model : str
        +embedder : object
        +target_schema : dict
        +prompt_template_str : str
        
        +canonicalize(triplets, sd_results, output_dir) tuple
        -_embed_relations(relations) ndarray
        -_compute_cosine(v1, v2) float
        -_verify_mapping(relation, candidate, context) bool
    }

    class JinaEmbedder {
        +model_name : str
        -api_key : str
        -base_url : str = "https://api.jina.ai/v1/embeddings"
        
        +encode(sentences, normalize) ndarray
        -_call_api(texts) list~list~
    }

    class SentenceTransformer {
        +encode(sentences, normalize_embeddings) ndarray
    }

    class llm_utils {
        <<module>>
        +api_chat_completion(model, system_prompt, history, temperature, max_tokens) str
        +openrouter_chat_completion(model, system_prompt, history, ...) str
        +openai_chat_completion(model, system_prompt, history, ...) str
        +is_jina_model(model_name) bool
        +is_model_openrouter(model_name) bool
    }

    class excel_to_txt {
        <<script>>
        +food_to_paragraph(row) str
        +convert(input_path, output_path, chunk_size)
        -NUTRIENTS : dict
        -DISEASE_THRESHOLDS : dict
    }

    class split_and_merge {
        <<script>>
        +split_file(input_path, n_parts)
        +parse_triples_from_dir(part_dir) list~list~
        +merge_results(output_base, n_parts, final_output)
    }

    class import_to_neo4j {
        <<script>>
        +load_triples(kg_file) list~list~
        +relation_to_cypher_type(relation) str
        +import_triples(triples, driver, database, label)
    }

    EDC "1" *-- "1" Extractor : oie_extractor
    EDC "1" *-- "1" SchemaDefiner : sd_definer
    EDC "1" *-- "1" SchemaCanonicalization : sc_canonicalizer
    
    SchemaCanonicalization --> JinaEmbedder : dùng nếu is_jina_model()
    SchemaCanonicalization --> SentenceTransformer : dùng nếu HF model
    
    Extractor ..> llm_utils : gọi api_chat_completion
    SchemaDefiner ..> llm_utils : gọi api_chat_completion
    SchemaCanonicalization ..> llm_utils : gọi api_chat_completion

    excel_to_txt ..> EDC : tạo input cho pipeline
    split_and_merge ..> EDC : gọi run.py theo part
    import_to_neo4j ..> SchemaCanonicalization : đọc output canon_kg.txt
```

---

## 5. SƠ ĐỒ ACTIVITY — QUY TRÌNH TRÍCH XUẤT KB THỰC PHẨM

```mermaid
flowchart TD
    Start(["🟢 Bắt đầu"]) --> CheckExcel

    CheckExcel{"File Excel\nđã có chưa?"}
    CheckExcel -->|Chưa| GetData["📥 Thu thập dữ liệu thực phẩm\nVietnam (163 món)"]
    GetData --> CheckExcel
    CheckExcel -->|Có| RunPrep

    RunPrep["🔄 Chạy excel_to_txt.py\nĐọc từng hàng Excel\n→ Tạo đoạn văn mô tả tiếng Việt\n→ Lưu food_vietnam.txt"]

    RunPrep --> ValidateTxt{"Kiểm tra\nfood_vietnam.txt"}
    ValidateTxt -->|"Thiếu dòng / lỗi encoding"| FixPrep["🔧 Sửa excel_to_txt.py\n(xử lý NaN, dấu phẩy thập phân)"]
    FixPrep --> RunPrep
    ValidateTxt -->|"✅ 162 dòng hợp lệ"| RunSplit

    RunSplit["✂️ Chạy split_and_merge.py split\n--parts 10\n→ Tạo part01..part10.txt\n→ In 10 lệnh run.py"]

    RunSplit --> Loop

    subgraph Loop["🔁 Vòng lặp — Chạy EDC cho mỗi part"]
        direction TB
        NextPart{"Còn part\nchưa xử lý?"}
        NextPart -->|Có| SetEnv["⚙️ Đặt biến môi trường\n$env:GROQ_KEY=...\n$env:JINA_KEY=..."]
        SetEnv --> RunEDC["🚀 python run.py\n--input part_i.txt\n--sc_embedder jina-embeddings-v3\n--output_dir output/part_i"]

        RunEDC --> Phase1["Phase 1: OIE\nGroq LLM trích xuất\nbộ ba (S, R, O) thô\ntừ mỗi đoạn văn"]
        Phase1 --> Phase2["Phase 2: SD\nGroq LLM định nghĩa\nngữ nghĩa quan hệ\ncho mỗi triple"]
        Phase2 --> CheckRate{"Rate limit\nGroq API?"}
        CheckRate -->|"429 + wait time"| ParseWait["⏳ Parse wait_time\ntừ error message\n(regex: 'try again in Xm Y.Zs')\nsleep(wait + 5s)"]
        ParseWait --> Phase2
        CheckRate -->|"200 OK"| Phase3

        Phase3["Phase 3: SC\nJina embed quan hệ\n→ Cosine với schema chuẩn\n→ LLM verify nếu cần\n→ Ánh xạ về 12 quan hệ"]

        Phase3 --> SaveCanon["💾 Lưu canon_kg.txt\noutput/part_i/iter0/\nMỗi dòng = list triples\ncủa 1 đoạn văn"]
        SaveCanon --> NextPart
        NextPart -->|"Không (tất cả xong)"| EndLoop
        EndLoop(["Kết thúc vòng lặp"])
    end

    Loop --> RunMerge

    RunMerge["🔀 Chạy split_and_merge.py merge\n--parts 10\n→ Đọc 10 canon_kg.txt\n→ ast.literal_eval mỗi dòng\n→ Flatten list of lists\n→ Exact dedup tuple(s,r,o)"]

    RunMerge --> CheckFlat{"kg_flat.txt\nhợp lệ?"}
    CheckFlat -->|"0 triples"| DebugMerge["🔍 Debug: Kiểm tra\ncanon_kg.txt có dữ liệu không"]
    DebugMerge --> RunMerge
    CheckFlat -->|"N > 0 triples"| StartNeo4j

    StartNeo4j["🐳 docker start nutrition_graph\nChờ Neo4j sẵn sàng (~15s)"]
    StartNeo4j --> RunImport

    RunImport["📤 python import_to_neo4j.py\n--kg_file kg_flat.txt\n--password password\n--label FoodVN"]

    RunImport --> CheckImport{"Kết nối\nthành công?"}
    CheckImport -->|"ServiceUnavailable"| StartNeo4j
    CheckImport -->|"AuthError"| FixPassword["🔧 Kiểm tra password\n(mặc định: 'password'\ntheo docker-compose.yml)"]
    FixPassword --> RunImport
    CheckImport -->|"✅ Connected"| Merge["MERGE nodes + relationships\nvào Neo4j"]

    Merge --> Verify["🔍 Kiểm tra Neo4j Browser\nhttp://localhost:7474\nMATCH (n:FoodVN)-[r]->(m:FoodVN)\nRETURN n,r,m LIMIT 50"]

    Verify --> TestAPI["🧪 Test API tư vấn\nPOST /api/chat\n{food: 'Gạo nếp cái',\ndisease: 'Tiểu đường'}"]

    TestAPI --> Done(["🔴 Kết thúc"])
```

---

## 6. SƠ ĐỒ THÀNH PHẦN (Component Diagram)

```mermaid
flowchart TB
    subgraph INPUT["📁 Dữ liệu đầu vào"]
        XLSX["food_vietnam_final.xlsx\n(163 món, ~20 cột dinh dưỡng)"]
        TXT_EN["diabetes_en.txt, gerd.txt...\n(Tài liệu y khoa tiếng Anh)"]
    end

    subgraph PREP["⚙️ Tiền xử lý"]
        E2T["excel_to_txt.py\n(openpyxl)"]
        PRE_EN["preprocess_document_en.py\n(sentence splitting)"]
        SPLIT["split_and_merge.py\n(split)"]
    end

    subgraph EDC_CORE["🧠 EDC Framework Core (edc/)"]
        FRAMEWORK["edc_framework.py\n(class EDC)"]
        EXTRACTOR["extract.py\n(class Extractor - OIE)"]
        DEFINER["define.py / sd module\n(Schema Definition)"]
        CANON["canonicalize.py\n(Schema Canonicalization)"]
        LLM_UTIL["utils/llm_utils.py\n(API routing: Groq / OpenRouter)"]
    end

    subgraph PROMPTS["📝 Prompt Resources"]
        OIE_TPL["prompt_templates/oie_template.txt"]
        SD_TPL["prompt_templates/sd_template.txt"]
        SC_TPL["prompt_templates/sc_template.txt"]
        OIE_FS["few_shot_examples/nutrition/\noie_few_shot_examples.txt"]
        SD_FS["few_shot_examples/gerd/\nsd_few_shot_examples.txt"]
        SCHEMA_VI["schemas/food_nutrition_schema.csv\n(12 quan hệ tiếng Việt)"]
        SCHEMA_EN["schemas/nutrition_schema.csv\n(15 quan hệ tiếng Anh)"]
    end

    subgraph EXTERNAL["☁️ External APIs"]
        GROQ["Groq API\nllama-3.3-70b-versatile\n(OIE + SD + SC verify)"]
        JINA["Jina AI API\njina-embeddings-v3\n(SC embedding)"]
    end

    subgraph OUTPUT["📤 Output & Storage"]
        CANON_KG["output/part_i/iter0/\ncanon_kg.txt"]
        MERGE_SCRIPT["split_and_merge.py (merge)\n→ kg_flat.txt"]
        IMPORT["import_to_neo4j.py\n(neo4j driver)"]
        NEO4J[("Neo4j 5.16\nFoodVN nodes\n+ TieuDuongKG")]
    end

    XLSX --> E2T --> food_txt["food_vietnam.txt"]
    TXT_EN --> PRE_EN --> eng_txt["processed_en.txt"]
    food_txt --> SPLIT --> parts["part01..part10.txt"]

    parts --> FRAMEWORK
    eng_txt --> FRAMEWORK
    FRAMEWORK --> EXTRACTOR --> LLM_UTIL --> GROQ
    FRAMEWORK --> DEFINER --> LLM_UTIL
    FRAMEWORK --> CANON --> LLM_UTIL
    CANON --> JINA

    OIE_TPL --> EXTRACTOR
    OIE_FS --> EXTRACTOR
    SD_TPL --> DEFINER
    SD_FS --> DEFINER
    SC_TPL --> CANON
    SCHEMA_VI --> CANON
    SCHEMA_EN --> CANON

    FRAMEWORK --> CANON_KG
    CANON_KG --> MERGE_SCRIPT
    MERGE_SCRIPT --> IMPORT --> NEO4J
```

---

## 7. SCHEMA ĐỊNH NGHĨA QUAN HỆ

### 7.1. Food Nutrition Schema (Luồng 2 — Tiếng Việt)

File: `edc-main/schemas/food_nutrition_schema.csv`

| STT | Quan hệ | Định nghĩa |
|-----|---------|-----------|
| 1 | `chứa` | Thực phẩm (subject) chứa dưỡng chất hoặc thành phần dinh dưỡng (object) |
| 2 | `giàu` | Thực phẩm (subject) là nguồn giàu dưỡng chất (object), hàm lượng cao hơn mức trung bình |
| 3 | `thuộc nhóm` | Thực phẩm (subject) thuộc nhóm hoặc loại thực phẩm (object) |
| 4 | `làm trầm trọng` | Thực phẩm (subject) có thể làm trầm trọng thêm hoặc tăng nguy cơ bệnh lý (object) |
| 5 | `được khuyến nghị cho` | Thực phẩm (subject) được khuyến nghị hoặc có lợi cho người mắc bệnh (object) |
| 6 | `cần hạn chế ở` | Bệnh nhân mắc bệnh (subject) cần hạn chế hoặc tránh sử dụng thực phẩm (object) |
| 7 | `phòng ngừa` | Thực phẩm hoặc dưỡng chất (subject) giúp phòng ngừa bệnh lý (object) |
| 8 | `nhiều` | Thực phẩm (subject) có hàm lượng cao của chỉ số dinh dưỡng (object) |
| 9 | `ít` | Thực phẩm (subject) có hàm lượng thấp của chỉ số dinh dưỡng (object) |
| 10 | `hỗ trợ` | Dưỡng chất hoặc thực phẩm (subject) hỗ trợ chức năng hoặc quá trình sinh lý (object) |
| 11 | `ảnh hưởng đường huyết` | Thực phẩm (subject) ảnh hưởng đến mức đường huyết theo chiều hướng (object) |
| 12 | `chống chỉ định với` | Thực phẩm (subject) chống chỉ định hoặc cần tránh hoàn toàn ở bệnh nhân mắc (object) |

### 7.2. Nutrition Schema (Luồng 1 — Tiếng Anh)

File: `edc-main/schemas/nutrition_schema.csv`

| Quan hệ | Ý nghĩa |
|---------|---------|
| `treats` | hỗ trợ điều trị |
| `prevents` | phòng ngừa |
| `aggravates` | làm trầm trọng |
| `recommended for` | được khuyến nghị cho |
| `contraindicated for` | chống chỉ định với |
| `deficiency causes` | thiếu hụt gây ra |
| `enhances absorption of` | tăng cường hấp thu |
| `restricts` | cần hạn chế ở (bệnh lý → thực phẩm/dưỡng chất) |
| `requires` | cần bổ sung ở |
| `contains` | cung cấp / chứa |
| `reduces` | làm giảm |
| `associated with` | là yếu tố nguy cơ của |
| `daily intake` | lượng khuyến nghị hàng ngày |
| `food source` | nguồn thực phẩm |
| `symptom of` | là triệu chứng của |

---

## 8. CẤU TRÚC THƯ MỤC MODULE KG

```
edc-main/
│
├── 📄 run.py                          # Entry point EDC pipeline
├── 📄 excel_to_txt.py                 # Excel → text paragraphs
├── 📄 split_and_merge.py              # Split input / Merge output KG
├── 📄 import_to_neo4j.py              # Flat triples → Neo4j
├── 📄 preprocess_document_en.py       # English doc preprocessing
├── 📄 postprocess_kg_en.py            # Semantic dedup via Jina embeddings
├── 📄 translate_kg_to_neo4j.py        # Translate EN→VI + import
│
├── 📁 edc/                            # EDC Framework core
│   ├── edc_framework.py               # Class EDC (orchestrator)
│   ├── extract.py                     # Class Extractor (OIE)
│   └── utils/
│       └── llm_utils.py               # API routing (Groq/OpenRouter/Jina)
│
├── 📁 datasets/                       # Input texts
│   ├── food_vietnam.txt               # 162 food descriptions (VI)
│   ├── food_vietnam_part01..10.txt    # Parts for batch processing
│   └── diabetes_en.txt, gerd.txt...   # Medical docs (EN)
│
├── 📁 schemas/                        # Relation schemas (CSV)
│   ├── food_nutrition_schema.csv      # 12 Vietnamese relations
│   ├── nutrition_schema.csv           # 15 English relations
│   └── gerd_schema_vi.csv             # GERD-specific schema
│
├── 📁 few_shot_examples/              # Few-shot prompts
│   ├── nutrition/oie_few_shot_examples.txt
│   ├── gerd/oie_few_shot_examples.txt
│   └── gerd/sd_few_shot_examples.txt
│
├── 📁 prompt_templates/               # LLM prompt templates
│   ├── oie_template.txt
│   ├── sd_template.txt
│   └── sc_template.txt
│
└── 📁 output/                         # Pipeline outputs
    ├── food_vietnam_kg/
    │   ├── part01/iter0/canon_kg.txt  # Per-part KG output
    │   ├── ...
    │   └── kg_flat.txt                # Final merged + deduped KG
    └── diabetes_en_kg/
        └── iter0/
            ├── oie_kg.txt
            ├── kg_deduplicated.txt
            └── kg_vi.txt              # Translated Vietnamese KG
```

---

## 9. MÔ TẢ DỮ LIỆU ĐẦU VÀO & ĐẦU RA

### 9.1. Định dạng đầu vào (`food_vietnam_partXX.txt`)

Mỗi dòng là một đoạn văn mô tả 1 món ăn, ví dụ:

```
Gạo nếp cái là một thực phẩm thuộc nhóm Ngũ cốc và sản phẩm chế biến từ chúng.
Thành phần dinh dưỡng trong 100g Gạo nếp cái bao gồm: năng lượng: 346.0 kcal,
protein: 8.6 g, chất béo: 1.5 g, carbohydrate: 74.9 g, chất xơ: 0.6 g, canxi: 14.0 mg,
phospho: 147.0 mg, sắt: 0.9 mg, natri: 5.0 mg, kali: 132.0 mg, vitamin B1: 0.2 mg.
Hàm lượng carbohydrate cao (74.9 g) trong Gạo nếp cái có thể ảnh hưởng đến đường huyết,
người bệnh tiểu đường cần thận trọng khi sử dụng.
```

### 9.2. Định dạng trung gian (`canon_kg.txt`)

Mỗi dòng là một danh sách Python các triple, tương ứng với 1 đoạn văn đầu vào:

```python
[['Gạo_nếp_cái', 'chứa', 'năng_lượng'], ['Gạo_nếp_cái', 'chứa', 'protein'],
 ['Gạo_nếp_cái', 'chứa', 'carbohydrate'], ['Gạo_nếp_cái', 'thuộc nhóm', 'Ngũ cốc'],
 ['Gạo_nếp_cái', 'ảnh hưởng đường huyết', 'tăng'], ['Gạo_nếp_cái', 'cần hạn chế ở', 'Tiểu đường']]
```

### 9.3. Định dạng flat (`kg_flat.txt`) — Input cho Neo4j

Mỗi dòng là **1 triple duy nhất** dạng list Python:

```python
['Gạo_nếp_cái', 'chứa', 'năng_lượng']
['Gạo_nếp_cái', 'chứa', 'protein']
['Gạo_nếp_cái', 'thuộc nhóm', 'Ngũ cốc']
['Gạo_nếp_cái', 'ảnh hưởng đường huyết', 'tăng']
```

### 9.4. Cấu trúc Neo4j sau khi import

```cypher
// Node
(:FoodVN {name: "Gạo_nếp_cái"})
(:FoodVN {name: "Tiểu_đường"})
(:FoodVN {name: "carbohydrate"})

// Relationship
(:FoodVN {name:"Gạo_nếp_cái"})-[:CẦN_HẠN_CHẾ_Ở {relation:"cần hạn chế ở"}]->(:FoodVN {name:"Tiểu_đường"})
(:FoodVN {name:"Gạo_nếp_cái"})-[:CHỨA {relation:"chứa"}]->(:FoodVN {name:"carbohydrate"})
```

---

## 10. CÁC VẤN ĐỀ KỸ THUẬT VÀ CÁCH XỬ LÝ

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-------------|-----------|
| **Rate limit Groq API** | Free tier: 10,000 tokens/phút | `llm_utils.py` parse thời gian chờ từ lỗi, auto-sleep |
| **Disk đầy (14GB model)** | `--sc_embedder` mặc định tải `e5-mistral-7b-instruct` (14.2GB) | Dùng `--sc_embedder jina-embeddings-v3` (API, không tải local) |
| **Encoding UTF-8** | Tiếng Việt bị lỗi trong pipeline gốc (ASCII) | Cấu hình `encoding="utf-8"` tất cả file read/write |
| **Trùng lặp triple** | Nhiều đoạn văn mô tả cùng quan hệ | Exact dedup bằng `set(tuple(s,r,o))` trong merge |
| **Neo4j không kết nối** | Container `nutrition_graph` bị tắt | `docker start nutrition_graph` và chờ 15s |
| **Format canon_kg.txt** | Mỗi dòng là list-of-lists, không phải flat | `split_and_merge.py` dùng `ast.literal_eval` + flatten |

---

*Tài liệu được tạo ngày: 24/02/2026*
