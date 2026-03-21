"""
preprocess_raw_data.py
======================
Pipeline làm sạch và chuẩn hóa dữ liệu thô (có chứa bảng biểu, danh sách)
thành dạng văn xuôi (prose) chuẩn mực bằng cách sử dụng LLM (Groq / Llama-3.3-70B).

Mục tiêu là giữ LẠI NGUYÊN VẸN toàn bộ nội dung y khoa (các chỉ số, đơn vị, thực phẩm),
loại bỏ các siêu dữ liệu (tác giả, tham khảo), và cấu trúc lại dưới dạng văn bản liền mạch 
để tương thích với hệ thống trích xuất Knowledge Graph (EDC Framework).

Cách dùng:
  python preprocess_raw_data.py \
      --input_file "./datasets/disease/obesity/obesity_raw.txt" \
      --output_file "./datasets/disease/obesity/obesity.txt"
"""

import os
import argparse
import logging
import openai

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# CORE FUNCTION: CHUẨN HÓA RAW DATA -> PROSE DÙNG LLM
# ─────────────────────────────────────────────────────────────

def build_standardization_prompt(raw_text: str) -> str:
    system_prompt = """Bạn là một chuyên gia ngôn ngữ học chuyên về dữ liệu y khoa và hệ thống tri thức (Knowledge Graph). 
Nhiệm vụ của bạn là chuyển đổi dữ liệu thô (bảng biểu, danh sách, ghi chú rời rạc) thành văn bản tự nhiên (prose) để phục vụ việc trích xuất thực thể và quan hệ.

CÁC NGUYÊN TẮC VÀNG (STRICT RULES):
1. BẢO TOÀN DỮ LIỆU ĐỊNH LƯỢNG: Tuyệt đối không lược bỏ bất kỳ con số, đơn vị (mg, %, ml/kg, g/ngày, lít/ngày), khoảng giới hạn hay ví dụ tính toán dinh dưỡng nào.
2. XỬ LÝ BẢNG MA TRẬN: Khi gặp bảng Markdown phân loại, bạn PHẢI đối chiếu cẩn thận từng ô. KHÔNG gộp chung thực phẩm giữa các cột.
3. CHIẾN THUẬT XỬ LÝ BẢNG: Viết theo cấu trúc: "Đối với nhóm [Tên hàng], thực phẩm [Tên cột] bao gồm [A, B, C]".
4. CHỐNG LẶP TỪ (ANTI-REPETITION): Không lặp lại cùng một cụm từ nối quá 2 lần trong một đoạn văn. Hãy sử dụng linh hoạt các từ đồng nghĩa.
5. CẤU TRÚC NGÔN NGỮ: Sử dụng cấu trúc câu rõ ràng (Chủ ngữ - Động từ - Vị ngữ) để hệ thống EDC Framework dễ nhận diện thực thể.
6. XỬ LÝ DANH SÁCH: Khi gặp danh sách thực phẩm dài, hãy gom chúng thành các câu có logic, đọc kỹ để không làm rớt bất kỳ món nào.
7. LOẠI BỎ THÔNG TIN RÁC (NOISE REMOVAL): TUYỆT ĐỐI KHÔNG đưa vào văn bản đầu ra Tên tác giả, chức danh, và toàn bộ phần "Tài liệu tham khảo" hoặc link URL.
8. BẮT BUỘC TRÍCH XUẤT THỰC ĐƠN ĐẦY ĐỦ: Khi gặp bảng "Thực đơn mẫu", bạn PHẢI liệt kê chính xác TỪNG GIỜ ĂN, TỪNG MÓN ĂN và TỪNG ĐỊNH LƯỢNG (gram, ml). KHÔNG ĐƯỢC tóm tắt hay gom chung.
9. CHỐNG BỎ SÓT VĂN XUÔI (PROSE COMPLETENESS): Bạn phải quét văn bản gốc từ chữ đầu tiên đến chữ cuối cùng. TUYỆT ĐỐI KHÔNG được lược bỏ các đoạn văn quy định về Lượng Nước, các nhóm chất, hay các nguyên tắc sinh hoạt.
10. CHỐNG BẪY NGOẶC ĐƠN (NO BRACKET DROPPING): Tuyệt đối không được bỏ qua hoặc tóm tắt các nội dung nằm trong ngoặc đơn `()`. Nếu bản gốc liệt kê danh sách thực phẩm, các loại bệnh, hoặc tỷ lệ phần trăm dinh dưỡng trong ngoặc đơn, bạn PHẢI trích xuất và biến chúng thành câu liệt kê hoàn chỉnh. (Ví dụ: Thay vì viết 'thức ăn giàu năng lượng', phải viết rõ 'thức ăn giàu năng lượng như đường mật, mứt, socôla...').

CẤM (NEVER DO):
- Không tóm tắt (Summarize) phần kiến thức y khoa, thực đơn, hay hướng dẫn sinh hoạt.
- Không được làm mất các ví dụ tính toán.
- Không tự ý thêm các nhận xét cá nhân hoặc tự sửa lỗi y khoa của bản gốc.
"""

    user_prompt = f"TÀI LIỆU THÔ CẦN XỬ LÝ:\n\n{raw_text}"
    return system_prompt, user_prompt


def standardize_with_llm(
    raw_text: str,
    groq_api_key: str,
    model: str = "llama-3.3-70b-versatile"
) -> str:
    """
    Gửi văn bản thô qua API của Groq để tái cấu trúc lại.
    """
    client = openai.OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=groq_api_key,
    )

    system_prompt, user_prompt = build_standardization_prompt(raw_text)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Đã khóa nhiệt độ ở mức 0.1 để chống "sáng tạo" và "tóm tắt"
            max_tokens=6000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Lỗi khi gọi API Groq: {e}")
        return ""


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def preprocess_raw(input_file: str, output_file: str):
    groq_key = os.environ.get("GROQ_KEY", "")
    if not groq_key:
        logger.error("Chưa cài đặt biến môi trường GROQ_KEY. Hãy set $env:GROQ_KEY trước khi chạy.")
        return

    # ── Đọc file ──
    logger.info(f"Đọc file dữ liệu thô: {input_file}")
    if not os.path.exists(input_file):
        logger.error(f"Không tìm thấy file: {input_file}")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        raw_text = f.read()
    logger.info(f"  Độ dài văn bản thô: {len(raw_text)} ký tự.")

    # ── Gọi LLM chuẩn hóa ──
    logger.info("Đang xử lý qua LLM (Groq) để chuẩn hóa cấu trúc thành văn xuôi...")
    cleaned_text = standardize_with_llm(raw_text, groq_api_key=groq_key)

    if not cleaned_text:
        logger.warning("Không nhận được nội dung từ LLM. Quá trình thất bại.")
        return

    # ── Ghi output ──
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(cleaned_text + "\n")

    logger.info(f"✅ Đã chuẩn hóa thành công và ghi vào: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script chuẩn hóa dữ liệu raw thành văn tự nhiên (prose)")
    parser.add_argument("--input_file", required=True, help="Đường dẫn đến file raw (.txt)")
    parser.add_argument("--output_file", required=True, help="Đường dẫn đến file output đã làm sạch (.txt)")
    
    args = parser.parse_args()

    preprocess_raw(
        input_file=args.input_file,
        output_file=args.output_file
    )