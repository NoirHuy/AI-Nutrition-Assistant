from app.database import get_db_driver

# Quan hệ "cần tránh / hạn chế" trong KG tiếng Việt
AVOID_RELATIONS = [
    "làm trầm trọng",
    "chống chỉ định với",
    "cần hạn chế ở",
    "là yếu tố nguy cơ của",
]


def get_all_kg_nodes() -> list[str]:
    """Lấy danh sách tất cả tên node trong TieuDuongKG (cho LLM semantic mapping)."""
    driver = get_db_driver()
    if not driver:
        return []
    with driver.session() as session:
        result = session.run("MATCH (n:TieuDuongKG) RETURN n.name AS name")
        return [record["name"] for record in result if record["name"]]


def get_dietary_advice(disease_name: str):
    """
    Lấy danh sách chất/thực phẩm cần tránh theo bệnh từ KG TieuDuongKG.
    """
    driver = get_db_driver()
    if not driver:
        return None

    query = """
    MATCH (a:TieuDuongKG)-[r]->(b:TieuDuongKG)
    WHERE toLower(b.name) CONTAINS toLower($name)
      AND toLower(r.relation) IN $avoid_relations
    RETURN collect(DISTINCT a.name) AS avoid_items
    UNION
    MATCH (a:TieuDuongKG)-[r]->(b:TieuDuongKG)
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
    Tìm node thực phẩm/dưỡng chất trong KG và lấy các quan hệ liên quan.
    """
    driver = get_db_driver()
    if not driver:
        return None

    query = """
    MATCH (a:TieuDuongKG)-[r]->(b:TieuDuongKG)
    WHERE toLower(a.name) CONTAINS toLower($name)
    RETURN a.name AS found_name, collect({relation: r.relation, target: b.name}) AS connections
    LIMIT 1
    """

    with driver.session() as session:
        result = session.run(query, name=food_name_input).single()
        if result and result["found_name"]:
            connections = result["connections"]
            return {
                "found_name": result["found_name"],
                "calories": "N/A",
                "gi": "N/A",
                "ingredients": [{"name": c["target"]} for c in connections]
            }

    return None


def get_node_relations(node_name: str):
    """Lấy tất cả quan hệ của một node cụ thể trong KG."""
    driver = get_db_driver()
    if not driver:
        return None

    query = """
    MATCH (a:TieuDuongKG)-[r]->(b:TieuDuongKG)
    WHERE a.name = $name
    RETURN a.name AS subject, r.relation AS relation, b.name AS object
    UNION
    MATCH (a:TieuDuongKG)-[r]->(b:TieuDuongKG)
    WHERE b.name = $name
    RETURN a.name AS subject, r.relation AS relation, b.name AS object
    """

    with driver.session() as session:
        results = session.run(query, name=node_name)
        triples = [{"subject": r["subject"], "relation": r["relation"], "object": r["object"]}
                   for r in results]
        return triples if triples else None
