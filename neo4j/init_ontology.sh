#!/bin/bash


docker cp ./frontend/public/ontology.owl soam-neo4j-1:/var/lib/neo4j/import/ontology.owl

set -e
# Wait until Neo4j is ready
sleep 30
# Load the ontology using APOC (ensure the credentials match NEO4J_AUTH)
cypher-shell -u neo4j -p test "CALL apoc.import.rdf('/var/lib/neo4j/import/ontology.owl', {format:'RDF/XML'})"
cypher-shell -u neo4j -p test "CALL apoc.import.rdf('/var/lib/neo4j/import/ontology.owl', {format:'RDF/XML'})"


call n10s.graphconfig.init()

CREATE CONSTRAINT n10s_unique_uri FOR (r:Resource) REQUIRE r.uri IS UNIQUE

call n10s.rdf.import.fetch( "https://github.com/vladtf/soam/blob/main/frontend/public/ontology.owl","RDF/XML")

MATCH (n) RETURN n


CALL semantics.importRDF("https://github.com/vladtf/soam/blob/main/frontend/public/ontology.owl", "RDF/XML",{ languageFilter: "en" })