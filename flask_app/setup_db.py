from neo4j import GraphDatabase
import logging

class Neo4j_FDO_Manager:
    def __init__(self, endpoint, name, pw):
        # Connect to the Neo4j database
        uri = endpoint
        self.driver = GraphDatabase.driver(uri, auth=(name, pw))
        logging.info("setup sucessful")

    def close(self):
        self.driver.close()

    def add_fdo(self, pid):
        with self.driver.session() as session:
            session.run("CREATE (:FDO {pid: $pid})", pid=pid)

    def add_orig_fdo(self, pid):
        with self.driver.session() as session:
            session.run("CREATE (:orig_FDO {pid: $pid})", pid=pid)

    def add_fdo_ops(self, pid):
        with self.driver.session() as session:
            session.run("CREATE (:Operation_FDO {pid: $pid})", pid=pid)

    def add_service_ops(self, pid):
        with self.driver.session() as session:
            session.run("CREATE (:Service_Operation {pid: $pid})", pid=pid)

    def add_type(self, pid):
        with self.driver.session() as session:
            session.run("CREATE (:Type {pid: $pid})", pid=pid)

    def create_fdo_has_operation_relationship(self, fdo_subject, fdo_object):
        with self.driver.session() as session:
            #Could add annotation to HAS_OPERATION edge, e.g. the attributes.
            session.run(
                """
                MATCH (p:FDO {pid: $fdo_subject}), (c:Operation_FDO {pid: $fdo_object})
                CREATE (p)-[:HAS_OPERATION]->(c) 
                CREATE (c)-[:IS_OPERATION_FOR]->(p) 
                """,
                fdo_subject=fdo_subject, fdo_object=fdo_object
            )

    def create_fdo_has_operation_with_service_ops_relationship(self, fdo_subject, service_ops):
        with self.driver.session() as session:
            #Could add annotation to HAS_OPERATION edge, e.g. the attributes.
            session.run(
                """
                MATCH (p:orig_FDO {pid: $fdo_subject}), (c:Service_Operation {pid: $service_ops})
                CREATE (p)-[:HAS_OPERATION]->(c) 
                CREATE (c)-[:IS_OPERATION_FOR]->(p) 
                """,
                fdo_subject=fdo_subject, service_ops=service_ops
            )

    def create_fdo_has_metadata_relationship(self, fdo_subject, fdo_object):
        with self.driver.session() as session:
            #Could add annotation to HAS_OPERATION edge, e.g. the attributes.
            session.run(
                """
                MATCH (p:orig_FDO {pid: $fdo_subject}), (c:orig_FDO {pid: $fdo_object})
                CREATE (p)-[:HAS_METADATA]->(c)
                """,
                fdo_subject=fdo_subject, fdo_object=fdo_object
            )

    def create_fdo_is_metadata_for_relationship(self, fdo_subject, fdo_object):
        with self.driver.session() as session:
            #Could add annotation to HAS_OPERATION edge, e.g. the attributes.
            session.run(
                """
                MATCH (p:orig_FDO {pid: $fdo_subject}), (c:orig_FDO {pid: $fdo_object})
                CREATE (p)-[:IS_METADATA_FOR]->(c) 
                """,
                fdo_subject=fdo_subject, fdo_object=fdo_object
            )

    def create_type_has_operation_relationship(self, type_subject, fdo_object):
        with self.driver.session() as session:
            #Could add annotation to HAS_OPERATION edge, e.g. the attributes.
            session.run(
                """
                MATCH (p:Type {pid: $type_subject}), (c:FDO {pid: $fdo_object})
                CREATE (p)-[:HAS_OPERATION]->(c) 
                """,
                type_subject=type_subject, fdo_object=fdo_object
            )

    def create_fdo_is_related_to_relationship(self, fdo_subject, fdo_object):
        with self.driver.session() as session:
            #Could add annotation to HAS_OPERATION edge, e.g. the attributes.
            session.run(
                """
                MATCH (p:FDO {pid: $fdo_subject}), (c:FDO {pid: $fdo_object})
                CREATE (p)-[:IS_RELATED_TO]->(c) 
                """,
                fdo_subject=fdo_subject, fdo_object=fdo_object
            )

    def node_exists(self, label, pid):
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (n:{label} {{pid: $pid}})
                RETURN COUNT(n) > 0 AS exists
                """,
                pid=pid
            )
            record = result.single()
            return record["exists"]

    def edge_exists(self, node1_id, node2_id, relationship_type):
        query = f"""
        MATCH (a)-[r:{relationship_type}]->(b)
        WHERE id(a) = $node1_id AND id(b) = $node2_id
        RETURN COUNT(r) > 0 AS exists
        """
        with self.driver.session() as session:
            result = session.run(query, node1_id=node1_id, node2_id=node2_id)
            return result.single()["exists"]
        
    def fetch_entire_graph(self):
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n)-[r]->(m)
                RETURN n, r, m
                UNION
                MATCH (n)
                WHERE NOT (n)--()
                RETURN n, null AS r, null AS m
                """
            )
            return [record for record in result]


    def fetch_associated_nodes(self, start_node_label=None, start_node_property=None, start_node_value=None, relationship=None, target_node_label=None):
        # Construct the Cypher query dynamically
        query = "MATCH "
        
        # Start node
        if start_node_label:
            query += f"(a:{start_node_label})"
        else:
            query += "(a)"
        
        # Relationship
        if relationship:
            query += f"-[:{relationship}]->"
        else:
            query += "-->"
        
        # Target node
        if target_node_label:
            query += f"(b:{target_node_label})"
        else:
            query += "(b)"
        
        # Add optional WHERE clause
        query += " WHERE 1=1"  # Start with a dummy condition for easy concatenation
        if start_node_property and start_node_value:
            query += f" AND a.{start_node_property} = $value"
        
        # Return target nodes
        query += " RETURN b"
        
        # Execute the query
        with self.driver.session() as session:
            results = session.run(query, value=start_node_value)
            return [record["b"] for record in results]
