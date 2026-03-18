"""
merge_dedup.py — Gộp các file canon_kg.txt từ nhiều parts, khử trùng lặp và
xuất ra file kg_flat.txt (mỗi dòng là 1 triple dạng ['s', 'r', 'o'])
để đưa vào import_to_neo4j.py.

Cách dùng:
  python merge_dedup.py \
      --parts output/food_vietnam_kg/part01 output/food_vietnam_kg/part02 \
      --output output/food_vietnam_kg/kg_flat.txt
"""

import ast
import argparse
import os
from pathlib import Path


def load_canon_kg(part_dir: str) -> list[list[str]]:
    """Đọc canon_kg.txt từ thư mục part, trả về list các triple."""
    canon_path = os.path.join(part_dir, "iter0", "canon_kg.txt")
    if not os.path.exists(canon_path):
        print(f"  ⚠️  Không tìm thấy: {canon_path}")
        return []

    triples = []
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
                            if all(triple):  # bỏ triple rỗng
                                triples.append(triple)
            except Exception as e:
                print(f"  ⚠️  Lỗi parse dòng: {line[:60]}... → {e}")
    return triples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parts", nargs="+", required=True,
                        help="Đường dẫn đến các thư mục part01, part02, ...")
    parser.add_argument("--output", default="output/food_vietnam_kg/kg_flat.txt",
                        help="File output (mỗi dòng 1 triple)")
    args = parser.parse_args()

    all_triples = []
    for part_dir in args.parts:
        triples = load_canon_kg(part_dir)
        print(f"✅ {part_dir}: {len(triples)} triples")
        all_triples.extend(triples)

    print(f"\n📊 Tổng trước dedup : {len(all_triples)}")

    # Exact dedup — dùng tuple để hashable
    seen = set()
    unique = []
    for t in all_triples:
        key = tuple(t)
        if key not in seen:
            seen.add(key)
            unique.append(t)

    print(f"📊 Sau dedup         : {len(unique)}")
    print(f"🗑️  Đã xóa           : {len(all_triples) - len(unique)} triples trùng")

    # Ghi ra file (mỗi dòng = 1 triple dạng ['s', 'r', 'o'])
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for t in unique:
            f.write(str(t) + "\n")

    print(f"\n✅ Đã lưu → {args.output}")
    print(f"\n📋 Bước tiếp theo — Import vào Neo4j:")
    print(f"   python import_to_neo4j.py \\")
    print(f"       --kg_file {args.output} \\")
    print(f"       --password <NEO4J_PASSWORD> \\")
    print(f"       --label TieuDuangKG")


if __name__ == "__main__":
    main()
