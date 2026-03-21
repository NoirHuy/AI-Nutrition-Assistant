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
            model="meta-llama/llama-4-scout-17b-16e-instruct",
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
    prompt = f"""Bạn có danh sách các node thực phẩm trong Knowledge Graph dinh dưỡng:
{nodes_str}

Người dùng hỏi về: "{user_input}"

NHIỆM VỤ: Hãy tìm ra ĐÚNG node đồng nghĩa, hoặc là nhóm nguyên liệu bao hàm cực kì sát với món này.
QUY TẮC NGHIÊM NGẶT (RẤT QUAN TRỌNG): 
- CHỈ mapping khi món của người dùng là tên gọi khác, hoặc là thực phẩm tương đương. (VD: "coca", "pepsi" -> "đồ_uống_có_đường" | "bò kho" -> "thịt bò").
- TUYỆT ĐỐI KHÔNG mapping dựa vào sự giống nhau về mặt chữ viết nếu bản chất món ăn khác xa nhau. (VD: "trứng cá tầm" KHÔNG ĐƯỢC map bừa bãi với "trứng" hay "cá", vì trứng cá tầm rất đặc thù).
- Nếu món ăn này xa lạ, không phổ biến ở VN, hoặc từ khóa trong danh sách không khớp 100% nghĩa, BẮT BUỘC trả về mảng rỗng [].

Chỉ trả về JSON array chứa tên node chính xác trong danh sách. Ví dụ: ["thịt bò"] hoặc []"""

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
    from app.services.graph_query import get_node_properties

    disease_map = {
        "béo phì (obesity)": "béo phì",
        "tiểu đường type 2": "tiểu đường",
        "cao huyết áp": "tăng huyết áp",
        "suy thận": "bệnh thận"
    }
    mapped_disease = disease_map.get(disease.lower().strip(), disease)

    # === BƯỚC 1: Truy vấn Neo4j trực tiếp ===
    disease_data = get_dietary_advice(mapped_disease)
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
        return {
            "bot_response": (
                f"⚠️ **Không tìm thấy dữ liệu trong Knowledge Graph** cho:\n"
                f"- Bệnh: **{disease}**\n- Thực phẩm: **{food_or_query}**\n\n"
                f"Vui lòng thử từ khóa khác."
            ),
            "nutrition": None
        }

    # Lấy thông số dinh dưỡng từ Neo4j truyền ra JSON
    nutrition_data = None
    if has_food_data:
        nutrition_data = {
            "name": food_data.get("found_name") or food_or_query,
            "calories": food_data.get("calories") or 0,
            "carbs": food_data.get("carbs") or 0,
            "protein": food_data.get("protein") or 0,
            "fat": food_data.get("fat") or 0,
            "iron": food_data.get("iron") or 0,
            "zinc": food_data.get("zinc") or 0,
            "fiber": food_data.get("fiber") or 0,
            "cholesterol": food_data.get("cholesterol") or 0,
            "calcium": food_data.get("calcium") or 0,
            "phosphorus": food_data.get("phosphorus") or 0,
            "potassium": food_data.get("potassium") or 0,
            "sodium": food_data.get("sodium") or 0,
            "vitamin_a": food_data.get("vitamin_a") or 0,
            "vitamin_b1": food_data.get("vitamin_b1") or 0,
            "vitamin_c": food_data.get("vitamin_c") or 0,
            "beta_carotene": food_data.get("beta_carotene") or 0
        }
    elif mapped_node_name:
        props = get_node_properties(mapped_node_name)
        if props and props.get("calories") is not None:
            nutrition_data = {
                "name": props.get("name") or mapped_node_name,
                "calories": props.get("calories") or 0,
                "carbs": props.get("carbs") or 0,
                "protein": props.get("protein") or 0,
                "fat": props.get("fat") or 0,
                "iron": props.get("iron") or 0,
                "zinc": props.get("zinc") or 0,
                "fiber": props.get("fiber") or 0,
                "cholesterol": props.get("cholesterol") or 0,
                "calcium": props.get("calcium") or 0,
                "phosphorus": props.get("phosphorus") or 0,
                "potassium": props.get("potassium") or 0,
                "sodium": props.get("sodium") or 0,
                "vitamin_a": props.get("vitamin_a") or 0,
                "vitamin_b1": props.get("vitamin_b1") or 0,
                "vitamin_c": props.get("vitamin_c") or 0,
                "beta_carotene": props.get("beta_carotene") or 0
            }

    # Nếu truy xuất Neo4j báo rỗng 100%: Dừng lại ngay không cho AI sáng tác
    if not has_food_data and not mapped_triples:
        fallback_nutrition = nutrition_data or {
            "name": food_or_query, "calories": 0, "carbs": 0, "protein": 0,
            "fat": 0, "iron": 0, "zinc": 0, "fiber": 0, "cholesterol": 0,
            "calcium": 0, "phosphorus": 0, "potassium": 0, "sodium": 0,
            "vitamin_a": 0, "vitamin_b1": 0, "vitamin_c": 0, "beta_carotene": 0
        }
        return {
            "bot_response": f"### 💡 Thông báo hệ thống\n\n⚠️ **Rất tiếc!** Món **{food_or_query}** hiện chưa có trong cơ sở dữ liệu Y bạ Dinh dưỡng. Để đảm bảo độ chính xác y khoa tuyệt đối, bạn có thể thử các món ăn hoặc nguyên liệu cốt lõi khác.",
            "nutrition": fallback_nutrition
        }

    # === BƯỚC 3: Xây dựng context từ graph ===
    graph_context = f"=== DỮ LIỆU TỪ KNOWLEDGE GRAPH (NEO4J) ===\n\n"
    graph_context += f"Câu hỏi người dùng: {food_or_query}\nBệnh lý: {disease}\n"

    if has_disease_data:
        avoid_list = "\n".join([f"  - {item}" for item in disease_data["avoid_nutrients"]])
        graph_context += f"\nCác yếu tố CẦN TRÁNH/HẠN CHẾ với {disease}:\n{avoid_list}\n"
    else:
        graph_context += f"\n(KG chưa có dữ liệu cần tránh cho bệnh {disease})\n"

    if has_food_data:
        connections = "\n".join([f"  - {item['name']}" for item in food_data["ingredients"]])
        graph_context += f"\nNode tìm thấy trong KG: {food_data['found_name']}\nCác thực thể liên quan:\n{connections}\n"
    elif mapped_triples:
        graph_context += f"\n'{food_or_query}' được ánh xạ sang node: '{mapped_node_name}'\nCác quan hệ trong KG:\n"
        for t in mapped_triples:
            graph_context += f"  - {t['subject']} --[{t['relation']}]--> {t['object']}\n"

    # === BƯỚC 4: LLM tạo sinh lời khuyên từ dữ liệu KG ===
    system_prompt = f"""Bạn là Bác sĩ dinh dưỡng chuyên nghiệp trực tiếp tư vấn cho người bệnh đang mắc {disease}. Dựa trên dữ liệu từ y bạ (Knowledge Graph) bên dưới, hãy đưa ra lời khuyên theo FORMAT quy định.

{graph_context}

QUY TẮC TỐI THƯỢNG:
1. Xưng hô tự nhiên, thân thiện và mang đậm chất chuyên môn y khoa.
2. NẾU MÓN ĂN AN TOÀN (KG KHÔNG BÁO CẦN TRÁNH): Tuyệt đối KHÔNG nói câu sáo rỗng như "Không có thông tin cụ thể", "Không có đề xuất thay thế". Bạn CHỈ CẦN đưa ra lời khuyên tốt nhất (cách chế biến, liều lượng) 1 cách vui vẻ.
3. NẾU MÓN NÀY NẰM TRONG DANH SÁCH CẦN TRÁNH: Bạn hãy khuyên họ nên hạn chế, TRÍCH DẪN từ dữ liệu, ĐỒNG THỜI tự động bật phần "📊 Gợi ý thay thế".
4. TẤT CẢ các câu chữ nhắc về "KG", "Knowledge Graph", "Neo4j", "Node"... là bí mật hệ thống. Tuyệt đối không để lộ cho bệnh nhân, hãy nói "Dựa trên nghiên cứu/Theo tài liệu y khoa...".

FORMAT BẮT BUỘC (Chỉ xuất thẻ Heading 3 cho đẹp):

### 💡 Lời khuyên Dinh Dưỡng
[Nội dung nhận xét chính về món này, cách tối ưu để bảo vệ sức khỏe cho bệnh nhân {disease}. Gạch đầu dòng rõ ràng nếu dài.]

[LƯU Ý: Nếu món này thuộc loại CẦN HẠN CHẾ VÀ CÓ ĐỀ XUẤT thay thế, thì hãy bổ sung thêm thẻ "### 📊 Gợi ý thực phẩm an toàn hơn" bên dưới. NẾU MÓN AN TOÀN, HÃY CẮT BỎ HOÀN TOÀN KHÚC NÀY ĐỂ GIAO DIỆN SẠCH SẼ, KHÔNG ĐƯỢC CHÈN HEADER RỖNG!]"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Phân tích '{food_or_query}' cho bệnh nhân bị {disease}."}
            ],
            temperature=0.3
        )
        bot_msg = completion.choices[0].message.content
    except Exception as e:
        bot_msg = f"📊 **Dữ liệu từ Knowledge Graph:**\n\n{graph_context}\n\n⚠️ **LỖI API (Groq LLM):** {str(e)}"

    return {
        "bot_response": bot_msg,
        "nutrition": nutrition_data
    }


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
