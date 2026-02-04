from groq import Groq
from app.config import settings
from app.services.graph_query import get_dietary_advice

# 1. Khởi tạo Client
client = None
try:
    if settings.GROQ_API_KEY:
        client = Groq(api_key=settings.GROQ_API_KEY)
        print("✅ Đã kết nối AI Server")
    else:
        print("⚠️ Chưa có API Key")
except Exception as e:
    print(f"❌ Lỗi kết nối Groq: {e}")

# ==========================================
# BƯỚC 1: DÙNG LLAMA-4 ĐỂ NHÌN ẢNH (VISION)
# ==========================================
def identify_food_from_image(image_base64: str):
    prompt = """
    Nhìn vào bức ảnh này và cho tôi biết chính xác:
    1. Tên món ăn là gì?
    2. Các thành phần nguyên liệu chính (ước lượng).
    3. Ước lượng Calo và lượng Đường/Tinh bột.
    
    Chỉ trả lời thông tin món ăn, không cần đưa ra lời khuyên y tế.
    """
    
    try:
        completion = client.chat.completions.create(
            # 👇 MODEL 1: CHUYÊN NHẬN DIỆN ẢNH
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
            temperature=0.5,
            max_completion_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"❌ Lỗi Vision: {e}")
        return None

# ==========================================
# BƯỚC 2: DÙNG GPT-OSS ĐỂ TƯ VẤN (REASONING)
# ==========================================
def generate_medical_advice(food_info: str, disease: str):
    # Lấy dữ liệu từ Neo4j (Graph)
    data = get_dietary_advice(disease)
    
    disease_context = f"Bệnh nhân bị bệnh: {disease}."
    if data:
        disease_context += f"\n- Các chất CẦN TRÁNH: {', '.join(data['avoid_nutrients'])}"
        disease_context += f"\n- Các món ĐẠI KỴ: {', '.join(data['avoid_foods'][:20])}"
    
    system_prompt = f"""
    Bạn là Bác sĩ Dinh dưỡng AI chuyên sâu (Sử dụng model GPT-OSS-120B).
    
    DỮ LIỆU BỆNH ÁN:
    {disease_context}
    
    THÔNG TIN MÓN ĂN (Từ Vision AI gửi sang):
    {food_info}
    
    NHIỆM VỤ:
    Dựa vào thông tin món ăn và hồ sơ bệnh lý trên, hãy đưa ra lời khuyên chi tiết:
    1. Người bệnh {disease} CÓ ĐƯỢC ĂN KHÔNG? (Trả lời Có/Không/Hạn chế)
    2. Giải thích tại sao dựa trên thành phần dinh dưỡng.
    3. Nếu ăn thì cần lưu ý gì?
    
    Văn phong: Chuyên gia, ân cần, dễ hiểu. Dùng icon sinh động.
    """

    try:
        completion = client.chat.completions.create(
            # 👇 MODEL 2: CHUYÊN LÝ LUẬN/GIẢI THÍCH
            model="openai/gpt-oss-120b", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Hãy phân tích và đưa ra lời khuyên."}
            ],
            temperature=0.7,
            max_completion_tokens=1000
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Lỗi Reasoning: {e}"

# ==========================================
# HÀM CHÍNH (MAIN FLOW)
# ==========================================
def analyze_image_diet(image_base64: str, disease: str):
    if not client: return "Lỗi Server: Chưa cấu hình API Key."

    # Bước 1: Gọi Model Vision để nhận diện món
    print("👀 Đang gọi Llama-4 Maverick để nhìn ảnh...")
    food_description = identify_food_from_image(image_base64)
    
    if not food_description:
        return "Xin lỗi, AI không nhìn rõ món ăn trong ảnh. Bạn chụp lại thử xem?"

    # Bước 2: Gọi Model GPT-OSS để tư vấn
    print(f"🧠 Đang gọi GPT-OSS-120B để tư vấn cho bệnh {disease}...")
    final_advice = generate_medical_advice(food_description, disease)
    
    return final_advice

# Hàm hỗ trợ chat text thường (nếu cần)
def generate_response(user_question: str, disease: str):
    # Logic tương tự Bước 2 nhưng input là câu hỏi người dùng
    return generate_medical_advice(user_question, disease)