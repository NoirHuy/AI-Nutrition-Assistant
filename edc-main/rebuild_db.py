import os
import subprocess
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "password"

def clear_db():
    print("🧹 Đang xóa trắng Neo4j Database...")
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("✅ Đã xóa toàn bộ Node và Relation.")
    except Exception as e:
        print(f"❌ Lỗi xóa DB: {e}")
    finally:
        driver.close()

def import_data():
    commands = []
    # Nhập Food KG và thuộc tính Dinh dưỡng từ Excel (10 phần)
    for i in range(1, 11):
        commands.append(f"python import_nutrition_kg.py --kg_file output/food_vietnam_kg/part{i:02d}/iter0/canon_kg.txt --excel ../docs/food_vietnam_final.xlsx --password password")
        
    commands.extend([
        # Nhập Disease KG (4 bệnh)
        "python import_nutrition_kg.py --kg_file output/disease_kg/diabetes/iter0/canon_kg_cleaned.txt --password password",
        "python import_nutrition_kg.py --kg_file output/disease_kg/hypertension/iter0/canon_kg_cleaned.txt --password password",
        "python import_nutrition_kg.py --kg_file output/disease_kg/kidney/iter0/canon_kg_cleaned.txt --password password",
        "python import_nutrition_kg.py --kg_file output/disease_kg/obesity/iter0/canon_kg_cleaned.txt --password password",
    ])
    
    for cmd in commands:
        print(f"\n🚀 Đang chạy: {cmd}")
        subprocess.run(cmd, shell=True, check=True)

if __name__ == "__main__":
    clear_db()
    import_data()
    print("\n🎉 HOÀN TẤT TOÀN BỘ QUÁ TRÌNH REBUILD TRÍ THỨC (KG)!")
