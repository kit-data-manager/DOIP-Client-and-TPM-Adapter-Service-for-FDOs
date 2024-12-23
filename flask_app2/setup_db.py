from neo4j import GraphDatabase



class Neo4j_FDO_Manager:
    def __init__(self):
        # Connect to the Neo4j database
        uri = "bolt://neo4j:7687"  # Change if Neo4j is running on a different host or port
        self.driver = GraphDatabase.driver(uri, auth=("neo4j", "testpassword"))
        print("setup sucessful")

    def close(self):
        self.driver.close()

    def add_fdo(self, pid):
        with self.driver.session() as session:
            session.run("CREATE (:FDO {pid: $pid})", pid=pid)

    def add_type(self, pid):
        with self.driver.session() as session:
            session.run("CREATE (:Type {pid: $pid})", pid=pid)

    def create_fdo_has_operation_relationship(self, fdo_subject, fdo_object):
        with self.driver.session() as session:
            #Could add annotation to HAS_OPERATION edge, e.g. the attributes.
            session.run(
                """
                MATCH (p:FDO {pid: $fdo_subject}), (c:FDO {pid: $fdo_object})
                CREATE (p)-[:HAS_OPERATION]->(c) 
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
