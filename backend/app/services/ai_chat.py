from groq import Groq
from app.config import settings
from app.services.graph_query import get_dietary_advice, get_food_nutrients

# Kết nối Client
client = None
try:
    if settings.GROQ_API_KEY:
        client = Groq(api_key=settings.GROQ_API_KEY)
except Exception as e:
    print(f"❌ Lỗi Config AI: {e}")

# --- VISION: DÙNG LLAMA-4 MAVERICK ---
def identify_food_name(image_base64: str):
    # Prompt ngắn gọn để lấy tên món
    prompt = "Đây là món ăn gì của Việt Nam? Chỉ trả lời ngắn gọn tên món. Ví dụ: Phở bò"
    
    try:
        completion = client.chat.completions.create(
            # 👇 MODEL 1: THEO YÊU CẦU CỦA BẠN
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

# --- REASONING: DÙNG GPT-OSS-120B ---
def generate_medical_advice(food_name: str, disease: str):
    # 1. Lấy dữ liệu từ Graph
    disease_data = get_dietary_advice(disease)
    food_graph_data = get_food_nutrients(food_name)
    
    # 2. Chuẩn bị ngữ cảnh
    context = f"Bệnh nhân bị: {disease}."
    if disease_data:
        context += f"\n- QUY TẮC CẤM (Từ Graph): {', '.join(disease_data['avoid_nutrients'])}"
    
    food_info = f"Món ăn: {food_name}"
    
    # Ưu tiên dữ liệu Graph nếu có
    if food_graph_data:
        food_info += f"\n(DỮ LIỆU GỐC TỪ GRAPH - ƯU TIÊN SỐ 1)"
        food_info += f"\n- Tên chuẩn: {food_graph_data['found_name']}"
        food_info += f"\n- Thành phần dinh dưỡng: {', '.join([n['name'] for n in food_graph_data['ingredients']])}"
    else:
        food_info += "\n(Món này chưa có trong Graph, hãy tự ước lượng)."

    # 3. Prompt Tư vấn
    system_prompt = f"""
    Bạn là Trợ lý Dinh dưỡng AI.
    
    DỮ LIỆU ĐẦU VÀO:
    {context}
    {food_info}
    
    YÊU CẦU:
    - Nếu có dữ liệu Graph, hãy điền chính xác vào bảng.
    - So sánh thành phần với "QUY TẮC CẤM". Nếu trùng -> Ghi "⚠️ VI PHẠM".
    
    FORMAT TRẢ LỜI (Markdown):
    ## 🍲 Kết quả: {food_name}
    | Thành phần | Đánh giá |
    |---|---|
    | ... | ... |
    **Lời khuyên:** ...
    """

    try:
        completion = client.chat.completions.create(
            # 👇 MODEL 2: THEO YÊU CẦU CỦA BẠN
            model="openai/gpt-oss-120b", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Phân tích ngay."}
            ],
            temperature=0.3
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Lỗi Tư vấn: {e}"

# --- MAIN ENTRY ---
def analyze_image_diet(image_base64: str, disease: str):
    if not client: return "Lỗi Server: Chưa có Key AI."
    
    # B1: Gọi Llama-4 Maverick
    detected_name = identify_food_name(image_base64)
    if not detected_name:
        return "⚠️ Không nhìn rõ ảnh. Vui lòng chụp lại hoặc nhập tên món."
    
    # B2: Gọi GPT-OSS-120B
    return generate_medical_advice(detected_name, disease)

def generate_response(user_text: str, disease: str):
    return generate_medical_advice(user_text, disease)