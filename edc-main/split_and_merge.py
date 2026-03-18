"""
split_and_merge.py — Cắt file txt thành N phần nhỏ, và gộp kết quả KG lại sau khi trích xuất.

Cách dùng:
  # Bước 1: Cắt file
  python split_and_merge.py split --input datasets/food_vietnam.txt --parts 10

  # Bước 2: Chạy EDC trên từng part (xem lệnh in ra sau khi split)

  # Bước 3: Gộp kết quả sau khi đã chạy xong tất cả parts
  python split_and_merge.py merge --output_dir output/food_vietnam_kg --parts 10
"""

import argparse
import ast
import os
import glob
import re

# ───────────────────────────── SPLIT ─────────────────────────────

def split_file(input_path: str, n_parts: int):
    with open(input_path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    total = len(lines)
    chunk = (total + n_parts - 1) // n_parts  # ceiling division

    base = os.path.splitext(input_path)[0]   # datasets/food_vietnam
    part_paths = []

    for i in range(n_parts):
        start = i * chunk
        end   = min(start + chunk, total)
        if start >= total:
            break
        part_path = f"{base}_part{i+1:02d}.txt"
        with open(part_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines[start:end]) + "\n")
        part_paths.append((i+1, part_path, end - start))
        print(f"✅ Part {i+1:2d}: {end-start:3d} dòng → {part_path}")

    print(f"\n📦 Đã cắt {total} dòng thành {len(part_paths)} file.\n")
    print("=" * 65)
    print("📋 Chạy từng file bằng các lệnh sau (trong thư mục edc-main):")
    print("=" * 65)

    schema = "./schemas/food_nutrition_schema.csv"
    oie_fs = "./few_shot_examples/nutrition/oie_few_shot_examples.txt"
    sd_fs  = "./few_shot_examples/gerd/sd_few_shot_examples.txt"
    model  = "llama-3.3-70b-versatile"

    for idx, path, n in part_paths:
        out = f"./output/food_vietnam_kg/part{idx:02d}"
        rel = os.path.relpath(path, "edc-main").replace("\\", "/") if "edc-main" in path else f"./{os.path.basename(path)}"
        rel = f"./datasets/{os.path.basename(path)}"
        print(f"\n# Part {idx} ({n} dòng)")
        print(f"python run.py \\")
        print(f"  --input_text_file_path {rel} \\")
        print(f"  --target_schema_path {schema} \\")
        print(f"  --oie_llm {model} \\")
        print(f"  --sd_llm {model} \\")
        print(f"  --sc_llm {model} \\")
        print(f"  --sc_embedder jina-embeddings-v3 \\")
        print(f"  --oie_few_shot_example_file_path {oie_fs} \\")
        print(f"  --sd_few_shot_example_file_path {sd_fs} \\")
        print(f"  --output_dir {out}")

    print("\n" + "=" * 65)
    print("Sau khi chạy xong tất cả, gộp kết quả bằng:")
    print(f"  python split_and_merge.py merge --parts {len(part_paths)}")
    print("=" * 65)


# ───────────────────────────── MERGE ─────────────────────────────

def parse_triples_from_dir(part_dir: str) -> list[list[str]]:
    """Đọc canon_kg.txt từ thư mục part, trả về list các triple [s, r, o]."""
    triples = []
    canon_path = os.path.join(part_dir, "iter0", "canon_kg.txt")
    if not os.path.exists(canon_path):
        print(f"  ⚠️  Không tìm thấy: {canon_path}")
        return []

    with open(canon_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = ast.literal_eval(line)
                # Mỗi dòng là list các triple: [['s','r','o'], ...]
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, list) and len(item) == 3:
                            triple = [str(x).strip() for x in item]
                            if all(triple):
                                triples.append(triple)
            except Exception as e:
                print(f"  ⚠️  Lỗi parse: {line[:60]}... → {e}")
    return triples


def merge_results(output_base: str, n_parts: int, final_output: str):
    all_triples = []
    found_parts = 0

    for i in range(1, n_parts + 1):
        part_dir = os.path.join(output_base, f"part{i:02d}")
        if not os.path.exists(part_dir):
            print(f"⏭️  Part {i:02d}: thư mục không tồn tại, bỏ qua")
            continue

        triples = parse_triples_from_dir(part_dir)
        print(f"✅ Part {i:02d}: {len(triples)} triples")
        all_triples.extend(triples)
        found_parts += 1

    # Dedup — dùng tuple để hashable
    seen = set()
    unique_triples = []
    for t in all_triples:
        key = tuple(t)
        if key not in seen:
            seen.add(key)
            unique_triples.append(t)

    # Ghi ra file — mỗi dòng 1 triple dạng ['s', 'r', 'o'] cho import_to_neo4j.py
    os.makedirs(os.path.dirname(final_output) or ".", exist_ok=True)
    with open(final_output, "w", encoding="utf-8") as f:
        for t in unique_triples:
            f.write(str(t) + "\n")

    print(f"\n🎉 Gộp xong!")
    print(f"   Parts tìm thấy : {found_parts}/{n_parts}")
    print(f"   Tổng triples   : {len(all_triples)}")
    print(f"   Sau dedup      : {len(unique_triples)}")
    print(f"   Đã xóa trùng   : {len(all_triples) - len(unique_triples)}")
    print(f"   File output    : {final_output}")
    print(f"\n📋 Import vào Neo4j:")
    print(f"   python import_to_neo4j.py --kg_file {final_output} --password <PASSWORD> --label FoodVN")


# ───────────────────────────── MAIN ─────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    # split
    sp = sub.add_parser("split", help="Cắt file txt thành N phần")
    sp.add_argument("--input",  default="datasets/food_vietnam.txt")
    sp.add_argument("--parts",  type=int, default=10)

    # merge
    mp = sub.add_parser("merge", help="Gộp kết quả từ các part")
    mp.add_argument("--output_dir",    default="output/food_vietnam_kg")
    mp.add_argument("--parts",         type=int, default=10)
    mp.add_argument("--final_output",  default="output/food_vietnam_kg/kg_final.txt")

    args = parser.parse_args()

    if args.command == "split":
        split_file(args.input, args.parts)
    elif args.command == "merge":
        merge_results(args.output_dir, args.parts, args.final_output)
    else:
        parser.print_help()
