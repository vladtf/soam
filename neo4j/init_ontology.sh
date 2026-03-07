#!/bin/bash
# Load the OWL ontology into Neo4j using the n10s (neosemantics) plugin.
# The ontology file must be mounted at /var/lib/neo4j/import/ontology.owl.
set -e

NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-verystrongpassword}"
CYPHER="cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD"

echo "⏳ Waiting for Neo4j to be ready..."
until $CYPHER "RETURN 1" > /dev/null 2>&1; do
  sleep 2
done

echo "🔧 Initializing n10s graph config..."
$CYPHER "CALL n10s.graphconfig.init({handleVocabUris: 'MAP', handleMultival: 'ARRAY', keepLangTag: false, keepCustomDataTypes: true});"

echo "🔧 Creating URI uniqueness constraint..."
$CYPHER "CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE;"

echo "📥 Importing OWL ontology..."
$CYPHER "CALL n10s.rdf.import.fetch('file:///var/lib/neo4j/import/ontology.owl', 'RDF/XML');"

echo "✅ Ontology import complete. Verifying..."
$CYPHER "MATCH (c) WHERE 'owl__Class' IN labels(c) RETURN c.uri AS class;"