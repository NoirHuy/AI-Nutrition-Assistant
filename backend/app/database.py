from neo4j import GraphDatabase
from app.config import settings

# Biến toàn cục lưu kết nối
_driver = None

def get_db_driver():
    """
    Tạo hoặc lấy kết nối tới Neo4j.
    """
    global _driver
    if _driver is None:
        try:
            _driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            # Thử kết nối xem có sống không
            _driver.verify_connectivity()
            print("✅ Đã kết nối thành công tới Neo4j!")
        except Exception as e:
            print(f"❌ Lỗi kết nối Neo4j: {e}")
            _driver = None
    return _driver

def close_driver():
    global _driver
    if _driver:
        _driver.close()
        _driver = None