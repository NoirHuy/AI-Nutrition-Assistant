from app.database import db

def get_dietary_advice(disease_name: str):
    print(f"🔍 Đang tìm kiếm thông tin cho bệnh: {disease_name}")
    
    # Query tìm món ăn nên tránh và nên ăn
    query = """
    MATCH (d:Disease) 
    WHERE toLower(d.name) CONTAINS toLower($disease)
    
    // 1. Tìm cái cần tránh (SHOULD_AVOID)
    OPTIONAL MATCH (d)-[:SHOULD_AVOID]->(n_bad:Nutrient)
    OPTIONAL MATCH (f_bad:Food)-[:CONTAINS]->(n_bad)
    
    // 2. Tìm cái nên ăn (RECOMMENDED) - (Dự phòng cho tương lai)
    OPTIONAL MATCH (d)-[:RECOMMENDED]->(n_good:Nutrient)
    OPTIONAL MATCH (f_good:Food)-[:CONTAINS]->(n_good)
    
    RETURN 
        d.name as disease,
        collect(DISTINCT n_bad.name) as avoid_nutrients,
        collect(DISTINCT f_bad.name) as avoid_foods,
        collect(DISTINCT n_good.name) as good_nutrients,
        collect(DISTINCT f_good.name) as recommended_foods
    """
    
    results = db.query(query, {"disease": disease_name})
    
    if not results or results[0]['disease'] is None:
        return None
        
    return results[0]