"""
preprocess_document.py
=======================
Pipeline tiền xử lý tài liệu cho EDC Framework.

Các bước:
  1. Chunking               : Chia tài liệu dài thành các đoạn ngắn (sentence-level).
  2. Coreference Resolution : Dùng LLM (Groq / Llama-3.3-70B) giải quyết đồng tham chiếu
                              cho từng chunk dựa trên ngữ cảnh đoạn trước (sliding window).
  3. Output                 : Ghi file .txt chuẩn cho EDC (mỗi dòng = 1 chunk đã xử lý).

Cách dùng:
  python preprocess_document.py \
      --input_file "./datasets/Hướng dẫn Chế độ ăn uống và Dinh dưỡng cho bệnh nhân tiểu đường.txt" \
      --output_file "./datasets/diabetes.txt" \
      --sentences_per_chunk 3 \
      --context_window 1
"""

import os
import re
import argparse
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# BƯỚC 0 (phụ): Làm sạch văn bản gốc
# ─────────────────────────────────────────────────────────────

def clean_raw_text(raw_text: str) -> str:
    """
    Loại bỏ tiêu đề, thông tin tác giả, header/footer báo khoa học,
    và gộp tất cả dòng thành một khối văn bản liên tục.
    """
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    skip_patterns = [
        r'^Hướng dẫn Chế độ ăn uống',  # tiêu đề
        r'^Katsumi',                     # tác giả
        r'Nutrients \d{4},',             # header bài báo
        r'^\d+/\d+$',                    # page number dạng "2/4"
        r'^\[\d',                        # reference [1], [2]...
    ]

    content_lines = []
    for line in lines:
        if any(re.search(pat, line) for pat in skip_patterns):
            continue
        content_lines.append(line)

    return " ".join(content_lines)


# ─────────────────────────────────────────────────────────────
# BƯỚC 1: CHUNKING — Tách câu cho tiếng Việt
# ─────────────────────────────────────────────────────────────

def split_into_sentences(text: str) -> list[str]:
    """
    Tách văn bản thành danh sách câu.
    Nhận diện dấu kết câu (.  !  ?) nhưng bỏ qua:
      - Số thập phân (0.8 g/kg)
      - Viết tắt phổ biến (g., mg., kg.)
    """
    # Bảo vệ số thập phân: 0.8 → 0<DOT>8
    text = re.sub(r'(\d)\.(\d)', r'\1<DOT>\2', text)
    # Bảo vệ viết tắt đơn vị: g., mg., kg.
    text = re.sub(r'\b(g|mg|kg|ml|kcal|vs|Dr|PGS|GS)\.\s', r'\1<DOT> ', text)

    # Tách theo dấu câu kết thúc
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    # Khôi phục và lọc mảnh quá ngắn
    sentences = [
        s.replace('<DOT>', '.').strip()
        for s in raw_sentences
        if s.strip() and len(s.strip()) > 10
    ]
    return sentences


def chunk_sentences(sentences: list[str], chunk_size: int = 3) -> list[str]:
    """
    Gom các câu thành các chunk có kích thước cố định.
    Chunk cuối có thể ngắn hơn nếu số câu không chia hết.
    """
    chunks = []
    for i in range(0, len(sentences), chunk_size):
        chunk = " ".join(sentences[i : i + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


# ─────────────────────────────────────────────────────────────
# BƯỚC 2: COREFERENCE RESOLUTION — Groq LLM
# ─────────────────────────────────────────────────────────────

def build_coreference_prompt(context_chunk: str, current_chunk: str) -> str:
    """
    Xây dựng prompt yêu cầu LLM thay thế đại từ / cụm tham chiếu
    bằng tên thực thể cụ thể, dựa trên ngữ cảnh đoạn trước.
    """
    if context_chunk:
        return f"""Bạn là công cụ giải quyết đồng tham chiếu (coreference resolution) cho văn bản tiếng Việt.

ĐOẠN NGỮ CẢNH TRƯỚC (dùng để tra cứu thực thể):
{context_chunk}

ĐOẠN CẦN XỬ LÝ:
{current_chunk}

NHIỆM VỤ:
- Đọc "ĐOẠN CẦN XỬ LÝ" và thay thế tất cả các đại từ, cụm từ tham chiếu mơ hồ \
(ví dụ: "nó", "điều này", "phương pháp này", "hướng dẫn này", "họ", "các khuyến nghị đó") \
bằng tên thực thể cụ thể lấy từ ngữ cảnh.
- Nếu đoạn cần xử lý đã rõ ràng, không cần thay đổi gì.
- Chỉ trả về đoạn văn đã được xử lý. KHÔNG thêm giải thích, KHÔNG thêm tiêu đề.

Đoạn đã xử lý:"""
    else:
        return f"""Bạn là công cụ giải quyết đồng tham chiếu (coreference resolution) cho văn bản tiếng Việt.

ĐOẠN CẦN XỬ LÝ:
{current_chunk}

NHIỆM VỤ:
- Thay thế các đại từ hoặc cụm tham chiếu mơ hồ bằng tên thực thể cụ thể \
nếu có thể suy ra từ chính đoạn văn.
- Nếu đoạn đã rõ ràng, không thay đổi gì.
- Chỉ trả về đoạn văn. KHÔNG thêm giải thích.

Đoạn đã xử lý:"""


def resolve_coreference_with_llm(
    chunks: list[str],
    groq_api_key: str,
    model: str = "llama-3.3-70b-versatile",
    context_window: int = 1,
    delay: float = 0.5,
) -> list[str]:
    """
    Giải quyết đồng tham chiếu cho tất cả chunks bằng Groq LLM.
    Mỗi chunk được xử lý với context_window chunks trước đó làm ngữ cảnh.

    Lý do dùng LLM thay vì LingMess:
      - LingMess được train trên tiếng Anh (OntoNotes), hiệu quả kém cho tiếng Việt.
      - Llama-3.3-70B hỗ trợ tiếng Việt tốt và có thể hiểu ngữ cảnh tham chiếu
        theo sliding window qua từng chunk.
    """
    import openai

    client = openai.OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=groq_api_key,
    )

    resolved_chunks = []

    for i, chunk in enumerate(chunks):
        logger.info(f"  Resolving coreference: chunk {i+1}/{len(chunks)}")

        # Lấy context từ các chunk đã được xử lý trước đó
        context_start = max(0, i - context_window)
        context = " ".join(resolved_chunks[context_start:i]) if resolved_chunks else ""

        prompt = build_coreference_prompt(context, chunk)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=512,
            )
            resolved = response.choices[0].message.content.strip()
            # Loại bỏ nếu LLM thêm prefix không mong muốn
            for prefix in ["Đoạn đã xử lý:", "Đoạn văn đã xử lý:"]:
                if resolved.startswith(prefix):
                    resolved = resolved[len(prefix):].strip()
            resolved_chunks.append(resolved)
        except Exception as e:
            logger.warning(f"    LLM error on chunk {i+1}: {e}. Keeping original.")
            resolved_chunks.append(chunk)

        # Tránh rate limit Groq
        time.sleep(delay)

    return resolved_chunks


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def preprocess(
    input_file: str,
    output_file: str,
    sentences_per_chunk: int = 3,
    context_window: int = 1,
    skip_coreference: bool = False,
):
    groq_key = os.environ.get("GROQ_KEY", "")

    # ── Đọc file ──
    logger.info(f"Đọc file: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # ── Làm sạch ──
    logger.info("Làm sạch văn bản gốc...")
    clean_text = clean_raw_text(raw_text)
    logger.info(f"  Văn bản sau làm sạch: {len(clean_text)} ký tự")

    # ── Bước 1: Chunking ──
    logger.info(f"Chunking ({sentences_per_chunk} câu/chunk)...")
    sentences = split_into_sentences(clean_text)
    logger.info(f"  Tổng số câu: {len(sentences)}")
    chunks = chunk_sentences(sentences, chunk_size=sentences_per_chunk)
    logger.info(f"  Tổng số chunk: {len(chunks)}")

    # ── Bước 2: Coreference Resolution ──
    if skip_coreference:
        logger.info("Bỏ qua coreference resolution (--skip_coreference).")
        processed_chunks = chunks
    elif not groq_key:
        logger.warning("GROQ_KEY không được đặt. Bỏ qua coreference resolution.")
        processed_chunks = chunks
    else:
        logger.info(f"Coreference resolution via Groq LLM (context_window={context_window})...")
        processed_chunks = resolve_coreference_with_llm(
            chunks,
            groq_api_key=groq_key,
            context_window=context_window,
        )

    # ── Ghi output ──
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        for chunk in processed_chunks:
            f.write(chunk.strip() + "\n")

    logger.info(f"✅ Đã ghi {len(processed_chunks)} chunks vào: {output_file}")
    return processed_chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tiền xử lý tài liệu cho EDC Framework")
    parser.add_argument("--input_file", required=True, help="Đường dẫn file .txt đầu vào")
    parser.add_argument("--output_file", required=True, help="Đường dẫn file .txt đầu ra cho EDC")
    parser.add_argument("--sentences_per_chunk", type=int, default=3,
                        help="Số câu mỗi chunk (mặc định: 3)")
    parser.add_argument("--context_window", type=int, default=1,
                        help="Số chunk trước dùng làm ngữ cảnh coref (mặc định: 1)")
    parser.add_argument("--skip_coreference", action="store_true",
                        help="Bỏ qua bước coreference resolution")
    args = parser.parse_args()

    preprocess(
        input_file=args.input_file,
        output_file=args.output_file,
        sentences_per_chunk=args.sentences_per_chunk,
        context_window=args.context_window,
        skip_coreference=args.skip_coreference,
    )
