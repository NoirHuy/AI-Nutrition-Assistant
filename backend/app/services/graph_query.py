from app.database import get_db_driver

# Quan hệ "cần tránh / hạn chế" trong KG tiếng Việt
AVOID_RELATIONS = [
    "làm trầm trọng",
    "chống chỉ định với",
    "cần hạn chế ở",
    "là yếu tố nguy cơ của",
]


def get_all_kg_nodes() -> list[str]:
    """Lấy danh sách tất cả tên node trong KG (cho LLM semantic mapping)."""
    driver = get_db_driver()
    if not driver:
        return []
    with driver.session() as session:
        result = session.run("MATCH (n) WHERE n.name IS NOT NULL RETURN collect(DISTINCT n.name) AS names")
        record = result.single()
        return record["names"] if record and record["names"] else []


def get_dietary_advice(disease_name: str):
    """
    Lấy danh sách chất/thực phẩm cần tránh theo bệnh từ KG.
    """
    driver = get_db_driver()
    if not driver:
        return None

    query = """
    MATCH (a)-[r]->(b)
    WHERE toLower(b.name) CONTAINS toLower($name)
      AND toLower(r.relation) IN $avoid_relations
    RETURN collect(DISTINCT a.name) AS avoid_items
    UNION
    MATCH (a)-[r]->(b)
    WHERE toLower(a.name) CONTAINS toLower($name)
      AND toLower(r.relation) IN $avoid_relations
    RETURN collect(DISTINCT b.name) AS avoid_items
    """

    with driver.session() as session:
        results = session.run(query, name=disease_name, avoid_relations=AVOID_RELATIONS)
        avoid_items = []
        for record in results:
            avoid_items.extend(record["avoid_items"])
        avoid_items = list(set(avoid_items))

        if avoid_items:
            return {
                "disease": disease_name,
                "avoid_nutrients": avoid_items,
                "avoid_foods": []
            }
    return None


def get_food_nutrients(food_name_input: str):
    """
    Tìm node thực phẩm/dưỡng chất trong KG và lấy các quan hệ liên quan cùng thông số dinh dưỡng.
    """
    driver = get_db_driver()
    if not driver:
        return None

    query = """
    MATCH (a)
    WHERE toLower(a.name) CONTAINS toLower($name) AND a.calories IS NOT NULL
    OPTIONAL MATCH (a)-[r]->(b)
    RETURN a.name AS found_name, 
           a.calories AS calories, a.carbs AS carbs, a.protein AS protein, a.fat AS fat,
           a.iron AS iron, a.zinc AS zinc, a.fiber AS fiber, a.cholesterol AS cholesterol,
           a.calcium AS calcium, a.phosphorus AS phosphorus, a.potassium AS potassium,
           a.sodium AS sodium, a.vitamin_a AS vitamin_a, a.vitamin_b1 AS vitamin_b1,
           a.vitamin_c AS vitamin_c, a.beta_carotene AS beta_carotene,
           collect(CASE WHEN r IS NOT NULL THEN {relation: r.relation, target: b.name} ELSE NULL END) AS connections
    LIMIT 1
    """

    with driver.session() as session:
        result = session.run(query, name=food_name_input).single()
        if result and result["found_name"]:
            conns = result["connections"]
            connections = [c for c in conns if c is not None] if conns else []
            return {
                "found_name": result["found_name"],
                "calories": result["calories"],
                "carbs": result["carbs"],
                "protein": result["protein"],
                "fat": result["fat"],
                "iron": result["iron"],
                "zinc": result["zinc"],
                "fiber": result["fiber"],
                "cholesterol": result["cholesterol"],
                "calcium": result["calcium"],
                "phosphorus": result["phosphorus"],
                "potassium": result["potassium"],
                "sodium": result["sodium"],
                "vitamin_a": result["vitamin_a"],
                "vitamin_b1": result["vitamin_b1"],
                "vitamin_c": result["vitamin_c"],
                "beta_carotene": result["beta_carotene"],
                "ingredients": [{"name": c["target"]} for c in connections if c]
            }

    return None

def get_node_properties(node_name: str):
    """Lấy tất cả properties của một node cụ thể."""
    driver = get_db_driver()
    if not driver: return {}
    with driver.session() as session:
        res = session.run("MATCH (n) WHERE n.name = $name RETURN n", name=node_name).single()
        if res and res["n"]:
            return dict(res["n"])
    return {}


def get_node_relations(node_name: str):
    """Lấy tất cả quan hệ của một node cụ thể trong KG."""
    driver = get_db_driver()
    if not driver:
        return None

    query = """
    MATCH (a)-[r]->(b)
    WHERE a.name = $name
    RETURN a.name AS subject, r.relation AS relation, b.name AS object
    UNION
    MATCH (a)-[r]->(b)
    WHERE b.name = $name
    RETURN a.name AS subject, r.relation AS relation, b.name AS object
    """

    with driver.session() as session:
        results = session.run(query, name=node_name)
        triples = [{"subject": r["subject"], "relation": r["relation"], "object": r["object"]}
                   for r in results]
        return triples if triples else None
