import json
from groq import Groq
from app.config import settings
from app.services.graph_query import get_dietary_advice, get_food_nutrients, get_all_kg_nodes, get_node_relations

# Kết nối Client
client = None
try:
    if settings.GROQ_API_KEY:
        client = Groq(api_key=settings.GROQ_API_KEY)
except Exception as e:
    print(f"❌ Lỗi Config AI: {e}")

# --- VISION: NHẬN DIỆN ẢNH MÓN ĂN ---
def identify_food_name(image_base64: str):
    prompt = "Đây là món ăn gì của Việt Nam? Chỉ trả lời ngắn gọn tên món. Ví dụ: Phở bò"
    try:
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }
            ],
            temperature=0.2,
            max_completion_tokens=50
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Lỗi Vision: {e}")
        return None


def map_input_to_kg_nodes(user_input: str, kg_nodes: list[str]) -> list[str]:
    """
    Dùng LLM để ánh xạ input của user sang các node KG phù hợp.
    VD: 'nước ngọt có ga' → ['đồ_uống_có_đường']
    """
    if not kg_nodes or not client:
        return []

    nodes_str = ", ".join(kg_nodes)
    prompt = f"""Bạn có danh sách các node trong Knowledge Graph dinh dưỡng:
{nodes_str}

Người dùng hỏi về: "{user_input}"

Nhiệm vụ: Tìm các node trong danh sách trên mà có thể LIÊN QUAN hoặc là DANH MỤC CHỨA '{user_input}'.
Ví dụ: 'nước ngọt có ga' → liên quan đến 'đồ_uống_có_đường'

Chỉ trả về JSON array tên node, không giải thích. Ví dụ: ["đồ_uống_có_đường", "đường"]
Nếu không có node nào liên quan, trả về: []"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200
        )
        raw = response.choices[0].message.content.strip()
        # Parse JSON array
        import re
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"⚠️ Semantic mapping error: {e}")
    return []


# --- CORE: TƯ VẤN DỰA TRÊN DỮ LIỆU NEO4J ---
def generate_medical_advice(food_or_query: str, disease: str):
    """
    Quy trình:
    1. Thử query trực tiếp Neo4j
    2. Nếu không tìm thấy → LLM map input sang KG node → query lại
    3. Nếu CÓ dữ liệu → LLM format kết quả, KHÔNG thêm thông tin ngoài KG
    4. Nếu vẫn không có → báo rõ ràng
    """
    # === BƯỚC 1: Truy vấn Neo4j trực tiếp ===
    disease_data = get_dietary_advice(disease)
    food_data = get_food_nutrients(food_or_query)

    has_disease_data = disease_data and disease_data.get("avoid_nutrients")
    has_food_data = food_data and food_data.get("found_name")

    # === BƯỚC 2: Nếu không tìm thấy → Semantic Mapping ===
    mapped_node_name = None
    mapped_triples = None
    if not has_food_data:
        kg_nodes = get_all_kg_nodes()
        matched_nodes = map_input_to_kg_nodes(food_or_query, kg_nodes)
        print(f"🔍 Semantic mapping '{food_or_query}' → {matched_nodes}")

        for node in matched_nodes:
            triples = get_node_relations(node)
            if triples:
                mapped_node_name = node
                mapped_triples = triples
                break

    if not has_disease_data and not has_food_data and not mapped_triples:
        return (
            f"⚠️ **Không tìm thấy dữ liệu trong Knowledge Graph** cho:\n"
            f"- Bệnh: **{disease}**\n"
            f"- Thực phẩm/truy vấn: **{food_or_query}**\n\n"
            f"Knowledge Graph hiện tại chỉ có dữ liệu về bệnh **tiểu đường**. "
            f"Vui lòng mở rộng KG hoặc thử từ khóa khác."
        )

    # === BƯỚC 3: Xây dựng context từ graph ===
    graph_context = f"=== DỮ LIỆU TỪ KNOWLEDGE GRAPH (NEO4J) ===\n\n"
    graph_context += f"Câu hỏi người dùng: {food_or_query}\n"
    graph_context += f"Bệnh lý: {disease}\n"

    if has_disease_data:
        avoid_list = "\n".join([f"  - {item}" for item in disease_data["avoid_nutrients"]])
        graph_context += f"\nCác yếu tố CẦN TRÁNH/HẠN CHẾ với {disease} (theo KG):\n{avoid_list}\n"
    else:
        graph_context += f"\n(KG chưa có dữ liệu cần tránh cho bệnh {disease})\n"

    if has_food_data:
        connections = "\n".join([f"  - {item['name']}" for item in food_data["ingredients"]])
        graph_context += f"\nNode tìm thấy trong KG: {food_data['found_name']}\n"
        graph_context += f"Các thực thể liên quan:\n{connections}\n"
    elif mapped_triples:
        graph_context += f"\n'{food_or_query}' được ánh xạ sang node KG: '{mapped_node_name}'\n"
        graph_context += f"Các quan hệ trong KG:\n"
        for t in mapped_triples:
            graph_context += f"  - {t['subject']} --[{t['relation']}]--> {t['object']}\n"
    else:
        graph_context += f"\n(Không tìm thấy '{food_or_query}' hoặc node tương đương trong KG)\n"

    # === BƯỚC 4: LLM tạo sinh lời khuyên từ dữ liệu KG ===
    system_prompt = f"""Bạn là chuyên gia dinh dưỡng viết lời khuyên cho bệnh nhân. Dựa trên dữ liệu từ Knowledge Graph bên dưới, hãy tạo phản hồi theo đúng FORMAT sau.

{graph_context}

FORMAT TRẢ LỜI BẮT BUỘC (Markdown):

## 🍽️ {food_or_query}

### 💡 Lời khuyên cho bệnh nhân {disease}
[Viết 2-3 câu lời khuyên tự nhiên, thân thiện như bác sĩ nói chuyện với bệnh nhân.
Dựa trên dữ liệu KG nhưng TUYỆT ĐỐI KHÔNG được nhắc đến: tên node, tên quan hệ, từ "KG", "Knowledge Graph", "ánh xạ", "node", "triple", tên kỹ thuật có dấu gạch dưới.
Chỉ dùng tên tự nhiên của món ăn/bệnh, ví dụ: "nước ngọt có ga" thay vì "đồ_uống_có_đường".]

### 📊 Dữ liệu từ Knowledge Graph
[Liệt kê ngắn gọn các node và quan hệ tìm được từ KG]"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Phân tích '{food_or_query}' cho bệnh nhân bị {disease}."}
            ],
            temperature=0.3  # Cho phép LLM diễn đạt tự nhiên hơn khi tạo lời khuyên
        )
        return completion.choices[0].message.content
    except Exception as e:
        # Fallback: trả thẳng dữ liệu graph nếu LLM lỗi
        return f"📊 **Dữ liệu từ Knowledge Graph:**\n\n{graph_context}"



# --- MAIN ENTRY POINTS ---
def analyze_image_diet(image_base64: str, disease: str):
    if not client:
        return "Lỗi Server: Chưa có API Key."
    detected_name = identify_food_name(image_base64)
    if not detected_name:
        return "⚠️ Không nhìn rõ ảnh. Vui lòng chụp lại hoặc nhập tên món."
    return generate_medical_advice(detected_name, disease)


def generate_response(user_text: str, disease: str):
    if not client:
        return "Lỗi Server: Chưa có API Key."
    return generate_medical_advice(user_text, disease)
