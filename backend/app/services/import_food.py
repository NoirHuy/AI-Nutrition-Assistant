import pandas as pd
from neo4j import GraphDatabase
from app.config import settings
import os

class Neo4jLoader:
    def __init__(self):
        # Kết nối đến Neo4j
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def import_food(self, excel_file_path):
        print(f"🔄 Đang đọc file Excel: {excel_file_path}...")
        
        # 1. Đọc file Excel
        try:
            df = pd.read_excel(excel_file_path, engine='openpyxl')
        except Exception as e:
            print(f"❌ Lỗi đọc file Excel: {e}")
            return
        
        # 2. Danh sách cột số cần làm sạch (Chuyển dấu phẩy thành dấu chấm)
        numeric_cols = [
            'Protein (g)', 'Fat (g)', 'Carbonhydrates (g)', 'Chất xơ (g)', 
            'Cholesterol (mg)', 'Canxi (mg)', 'Photpho (mg)', 'Sắt (mg)', 
            'Natri (mg)', 'Kali (mg)', 'Beta Caroten (mcg)', 'Vitamin A (mcg)', 
            'Vitamin B1 (mg)', 'Vitamin C (mg)'
        ]

        # Xử lý làm sạch data
        for col in numeric_cols:
            if col in df.columns:
                # Ép kiểu về string để xử lý thay thế, rồi chuyển về số
                df[col] = df[col].astype(str).str.replace(',', '.').replace('nan', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 3. Mapping tên cột tiếng Việt sang tiếng Anh
        col_map = {
            'TÊN THỨC ĂN': 'name',
            'Calories (kcal)': 'calories',
            'Protein (g)': 'protein',
            'Fat (g)': 'lipid',
            'Carbonhydrates (g)': 'carbs',
            'Chất xơ (g)': 'fiber',
            'Cholesterol (mg)': 'cholesterol',
            'Canxi (mg)': 'calcium',
            'Photpho (mg)': 'phosphorus',
            'Sắt (mg)': 'iron',
            'Natri (mg)': 'sodium',
            'Kali (mg)': 'potassium',
            'Beta Caroten (mcg)': 'beta_carotene',
            'Vitamin A (mcg)': 'vitamin_a',
            'Vitamin B1 (mg)': 'vitamin_b1',
            'Vitamin C (mg)': 'vitamin_c',
            'Loại': 'category'
        }
        df.rename(columns=col_map, inplace=True)

        print("🚀 Bắt đầu nạp vào Neo4j...")
        with self.driver.session() as session:
            # 4. Tạo ràng buộc (SỬA LỖI CÚ PHÁP Ở ĐÂY)
            # Neo4j 5 yêu cầu phải đặt tên cho constraint (food_uniq, cat_uniq)
            try:
                session.run("CREATE CONSTRAINT food_uniq IF NOT EXISTS FOR (f:Food) REQUIRE f.name IS UNIQUE")
                session.run("CREATE CONSTRAINT cat_uniq IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE")
            except Exception as e:
                print(f"⚠️ Cảnh báo Constraint (có thể bỏ qua): {e}")

            count = 0
            for index, row in df.iterrows():
                # 5. Câu lệnh Cypher để tạo Node và Quan hệ
                query = """
                MERGE (c:Category {name: $category})
                MERGE (f:Food {name: $name})
                SET f += {
                    calories: $calories,
                    protein: $protein,
                    lipid: $lipid,
                    carbs: $carbs,
                    fiber: $fiber,
                    cholesterol: $cholesterol,
                    calcium: $calcium,
                    phosphorus: $phosphorus,
                    iron: $iron,
                    sodium: $sodium,
                    potassium: $potassium,
                    beta_carotene: $beta_carotene,
                    vitamin_a: $vitamin_a,
                    vitamin_b1: $vitamin_b1,
                    vitamin_c: $vitamin_c
                }
                MERGE (f)-[:BELONGS_TO]->(c)
                """
                
                # Chuyển row thành dict
                params = row.to_dict()
                
                # Neo4j không nhận giá trị NaN, thay bằng 0 hoặc string rỗng
                for k, v in params.items():
                    if pd.isna(v): params[k] = 0
                
                session.run(query, params)
                count += 1
                if count % 10 == 0:
                    print(f"   -> Đã nạp {count} món: {params['name']}")

        print(f"✅ HOÀN TẤT! Đã nạp thành công {count} món ăn vào Đồ thị.")

if __name__ == "__main__":
    loader = Neo4jLoader()
    # Chạy import với file Excel
    loader.import_food("food_data.xlsx")
    loader.close()