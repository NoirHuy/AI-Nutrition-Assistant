"""
import_to_neo4j.py
==================
Import KG triples from kg_deduplicated.txt into Neo4j.

Each triple ['subject', 'relation', 'object'] becomes:
  - (Subject:Entity) -[:RELATION]-> (Object:Entity)

Requirements:
  pip install neo4j

Usage:
  python import_to_neo4j.py \\
      --kg_file "./output/diabetes_en_kg/iter0/kg_deduplicated.txt" \\
      --uri "bolt://localhost:7687" \\
      --user "neo4j" \\
      --password "your_password" \\
      --database "neo4j"
"""

import ast
import re
import argparse
import logging
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def load_triples(kg_file: str) -> list[list[str]]:
    """Read kg_deduplicated.txt — each line is ['s', 'r', 'o']."""
    triples = []
    with open(kg_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = ast.literal_eval(line)
                if isinstance(parsed, list) and len(parsed) == 3:
                    triples.append([str(x) for x in parsed])
            except Exception as e:
                logger.debug(f"Skipping line: {line} — {e}")
    return triples


def relation_to_cypher_type(relation: str) -> str:
    """
    Convert relation string to a valid Neo4j relationship type.
    e.g. 'recommended for' -> 'RECOMMENDED_FOR'
         'daily intake'    -> 'DAILY_INTAKE'
    """
    cleaned = re.sub(r"[^a-zA-Z0-9\s_]", "", relation)
    return cleaned.strip().upper().replace(" ", "_")


# ─────────────────────────────────────────────────────────────
# Neo4j Import
# ─────────────────────────────────────────────────────────────

def import_triples(triples: list[list[str]], driver, database: str, label: str = "Entity"):
    """
    Batch import all triples into Neo4j.
    Uses MERGE to avoid duplicate nodes/edges.
    """
    with driver.session(database=database) as session:
        # Create constraint for uniqueness (run once)
        try:
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_name IF NOT EXISTS "
                f"FOR (n:`{label}`) REQUIRE n.name IS UNIQUE"
            )
            logger.info("Constraint created (or already exists.).")
        except Exception as e:
            logger.debug(f"Constraint note: {e}")

        success = 0
        failed = 0

        for s, r, o in triples:
            rel_type = relation_to_cypher_type(r)
            query = (
                f"MERGE (a:`{label}` {{name: $subject}}) "
                f"MERGE (b:`{label}` {{name: $object}}) "
                f"MERGE (a)-[:`{rel_type}` {{relation: $relation}}]->(b)"
            )
            try:
                session.run(query, subject=s, object=o, relation=r)
                success += 1
            except Exception as e:
                logger.warning(f"Failed triple ({s}, {r}, {o}): {e}")
                failed += 1

        logger.info(f"✅ Imported: {success} triples | Failed: {failed}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Import KG triples into Neo4j")
    parser.add_argument("--kg_file", required=True,
                        help="Path to kg_deduplicated.txt")
    parser.add_argument("--uri", default="bolt://localhost:7687",
                        help="Neo4j Bolt URI (default: bolt://localhost:7687)")
    parser.add_argument("--user", default="neo4j",
                        help="Neo4j username (default: neo4j)")
    parser.add_argument("--password", required=True,
                        help="Neo4j password")
    parser.add_argument("--database", default="neo4j",
                        help="Neo4j database name (default: neo4j)")
    parser.add_argument("--label", default="Entity",
                        help="Node label to use (default: Entity). Use different labels to separate KGs.")
    args = parser.parse_args()

    # Load triples
    logger.info(f"Loading KG from: {args.kg_file}")
    triples = load_triples(args.kg_file)
    logger.info(f"Total triples to import: {len(triples)}")

    if not triples:
        logger.warning("No triples found. Check your input file.")
        return

    # Connect & import
    logger.info(f"Connecting to Neo4j at {args.uri}...")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))

    try:
        driver.verify_connectivity()
        logger.info("Connection successful.")
        import_triples(triples, driver, args.database, args.label)
    finally:
        driver.close()

    # Print summary
    print(f"\n📊 Import Summary:")
    print(f"   File    : {args.kg_file}")
    print(f"   Neo4j   : {args.uri} / db={args.database}")
    print(f"   Triples : {len(triples)}")
    print(f"\n🔍 Cypher to explore:")
    print(f"   MATCH (n:Entity)-[r]->(m:Entity) RETURN n, r, m LIMIT 50")


if __name__ == "__main__":
    main()
