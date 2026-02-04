from neo4j import GraphDatabase
from app.config import settings

class Neo4jConnection:
    def __init__(self):
        self.driver = None

    def connect(self):
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            print("✅ Đã kết nối thành công tới Neo4j!")
        except Exception as e:
            print(f"❌ Lỗi kết nối Neo4j: {e}")

    def close(self):
        if self.driver:
            self.driver.close()

    def query(self, query, parameters=None):
        if not self.driver:
            self.connect()
            
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]

# --- DÒNG QUAN TRỌNG NHẤT BẠN ĐANG THIẾU LÀ Ở ĐÂY: ---
db = Neo4jConnection()