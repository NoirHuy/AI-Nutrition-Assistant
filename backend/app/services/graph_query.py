from app.database import get_db_driver

def get_dietary_advice(disease_name: str):
    """
    Lấy danh sách chất cần tránh và món ăn kỵ cho một loại bệnh.
    """
    driver = get_db_driver()
    if not driver:
        return None

    query = """
    MATCH (d:Disease)
    WHERE toLower(d.name) CONTAINS toLower($name)
    OPTIONAL MATCH (d)-[:AVOIDS]->(n:Nutrient)
    OPTIONAL MATCH (d)-[:SHOULD_LIMIT]->(f:Food)
    RETURN d.name AS disease, 
           collect(DISTINCT n.name) AS avoid_nutrients,
           collect(DISTINCT f.name) AS avoid_foods
    """
    
    with driver.session() as session:
        result = session.run(query, name=disease_name).single()
        if result and result["disease"]:
            return {
                "disease": result["disease"],
                "avoid_nutrients": result["avoid_nutrients"],
                "avoid_foods": result["avoid_foods"]
            }
    return None

def get_food_nutrients(food_name_input: str):
    """
    Tìm món ăn trong Graph và lấy chi tiết thành phần dinh dưỡng.
    """
    driver = get_db_driver()
    if not driver: return None

    # 1. Tìm tên món chuẩn trong DB (Lấy món gần giống nhất)
    query_find_food = """
    MATCH (f:Food)
    WHERE toLower(f.name) CONTAINS toLower($name)
    RETURN f.name AS name, f.calories AS cal, f.glycemic_index AS gi
    LIMIT 1
    """
    
    # 2. Lấy các chất dinh dưỡng của món đó
    query_get_nutrients = """
    MATCH (f:Food {name: $exact_name})-[:CONTAINS]->(n:Nutrient)
    RETURN n.name AS nutrient
    """
    
    with driver.session() as session:
        # Bước 1: Tìm tên
        food_node = session.run(query_find_food, name=food_name_input).single()
        
        if food_node:
            exact_name = food_node["name"]
            # Bước 2: Lấy chất
            nutrients_result = session.run(query_get_nutrients, exact_name=exact_name)
            # Gom lại thành list
            nutrients_list = [{"name": record["nutrient"]} for record in nutrients_result]
            
            return {
                "found_name": exact_name,
                "calories": food_node.get("cal", "N/A"),
                "gi": food_node.get("gi", "N/A"),
                "ingredients": nutrients_list
            }
        
    return None # Trả về None nếu không tìm thấy món nào