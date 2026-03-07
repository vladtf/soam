"""
Ontology Service — parses the OWL file and exposes schema metadata.

Provides class/property introspection so other components can validate
data against the ontology without hardcoding labels or types.
"""
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Any

from rdflib import Graph, RDF, RDFS, OWL, XSD, Namespace, URIRef

from src.utils.logging import get_logger

logger = get_logger(__name__)

SMARTCITY = Namespace("http://example.org/smartcity#")

# Map XSD types to Python type names for validation
XSD_TYPE_MAP: Dict[str, str] = {
    str(XSD.float): "float",
    str(XSD.double): "float",
    str(XSD.decimal): "float",
    str(XSD.integer): "int",
    str(XSD.string): "str",
    str(XSD.dateTime): "datetime",
    str(XSD.boolean): "bool",
}


class OntologyService:
    """Facade for OWL schema introspection."""

    def __init__(self, owl_path: str) -> None:
        self._graph = Graph()
        self._graph.parse(owl_path, format="xml")
        logger.info("✅ Parsed OWL ontology from %s (%d triples)", owl_path, len(self._graph))

    def get_classes(self) -> List[Dict[str, str]]:
        """Return all OWL classes with URI, label, and comment."""
        classes = []
        for cls in self._graph.subjects(RDF.type, OWL.Class):
            label = str(self._graph.value(cls, RDFS.label) or str(cls).split("#")[-1])
            comment = str(self._graph.value(cls, RDFS.comment) or "")
            # Check for subClassOf
            parent = self._graph.value(cls, RDFS.subClassOf)
            parent_uri = str(parent) if parent else None
            classes.append({
                "uri": str(cls),
                "label": label,
                "comment": comment,
                "subClassOf": parent_uri,
            })
        return classes

    def get_properties_for_class(self, class_uri: str) -> List[Dict[str, str]]:
        """Return all data/object properties whose rdfs:domain matches class_uri."""
        target = URIRef(class_uri)
        props = []
        for prop in self._graph.subjects(RDFS.domain, target):
            label = str(self._graph.value(prop, RDFS.label) or str(prop).split("#")[-1])
            range_val = self._graph.value(prop, RDFS.range)
            prop_type = "object" if (prop, RDF.type, OWL.ObjectProperty) in self._graph else "data"
            props.append({
                "uri": str(prop),
                "label": label,
                "range": str(range_val) if range_val else None,
                "type": prop_type,
                "python_type": XSD_TYPE_MAP.get(str(range_val)) if range_val else None,
            })
        return props

    def get_canonical_property_names(self) -> List[str]:
        """Return all DatatypeProperty local names (e.g., ['temperature', 'humidity', ...])."""
        names = []
        for prop in self._graph.subjects(RDF.type, OWL.DatatypeProperty):
            names.append(str(prop).split("#")[-1])
        return names

    def get_class_names(self) -> List[str]:
        """Return local names of all OWL classes."""
        return [str(cls).split("#")[-1] for cls in self._graph.subjects(RDF.type, OWL.Class)]

    def get_full_schema(self) -> Dict[str, Any]:
        """Return the complete schema as a JSON-serializable dict."""
        classes = self.get_classes()
        schema: Dict[str, Any] = {"classes": []}
        for cls in classes:
            props = self.get_properties_for_class(cls["uri"])
            schema["classes"].append({**cls, "properties": props})
        return schema

    def is_valid_sensor_type(self, type_name: str) -> bool:
        """Check if type_name is 'Sensor' or a subclass of Sensor."""
        sensor_uri = SMARTCITY.Sensor
        type_uri = SMARTCITY[type_name]
        if type_uri == sensor_uri:
            return True
        return (type_uri, RDFS.subClassOf, sensor_uri) in self._graph


@lru_cache()
def get_ontology_service() -> OntologyService:
    """Singleton factory — searches for ontology.owl in known locations."""
    search_paths = [
        Path("/app/ontology.owl"),
        Path(__file__).parent.parent.parent.parent / "frontend" / "public" / "ontology.owl",
    ]
    for path in search_paths:
        if path.exists():
            return OntologyService(str(path))
    raise FileNotFoundError(f"ontology.owl not found in: {search_paths}")
