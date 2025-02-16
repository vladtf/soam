import React, { useEffect, useState } from 'react';
import * as rdflib from 'rdflib';
import { Form, Button, Spinner, Alert } from 'react-bootstrap';

interface FormField {
  propertyURI: string;
  label: string;
  xsdType: string;
}

interface SensorFormData {
  [propertyURI: string]: string;
}

const SENSOR_CLASS = 'http://example.org/smartcity#Sensor';
const RDFS_DOMAIN = 'http://www.w3.org/2000/01/rdf-schema#domain';
const RDFS_RANGE = 'http://www.w3.org/2000/01/rdf-schema#range';
const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';

const DynamicSensorForm: React.FC = () => {
  const [fields, setFields] = useState<FormField[]>([]);
  const [formData, setFormData] = useState<SensorFormData>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Load the ontology and extract Sensor properties
  useEffect(() => {
    const loadOntology = async () => {
      try {
        const store = rdflib.graph();
        const fetcher = new rdflib.Fetcher(store, { fetch: window.fetch.bind(window) });
        const owlUrl = `${window.location.origin}/ontology.owl`;
        await fetcher.load(owlUrl);

        // Query: Find all datatype properties with domain Sensor
        // We iterate over statements with predicate rdfs:domain and object SENSOR_CLASS.
        const domainStatements = store.statementsMatching(undefined, rdflib.sym(RDFS_DOMAIN), rdflib.sym(SENSOR_CLASS));
        const extractedFields: FormField[] = [];

        domainStatements.forEach(stmt => {
          const propertyURI = stmt.subject.value;
          // Get a human-readable label, if available
          const labelNode = store.any(rdflib.sym(propertyURI), rdflib.sym(RDFS_LABEL));
          const label = labelNode ? labelNode.value : propertyURI;
          // Get the range of the property (assumed to be an XSD type)
          const rangeNode = store.any(rdflib.sym(propertyURI), rdflib.sym(RDFS_RANGE));
          const xsdType = rangeNode ? rangeNode.value : '';

          extractedFields.push({ propertyURI, label, xsdType });
        });

        setFields(extractedFields);
        setLoading(false);
      } catch (err: unknown) {
        console.error('Error loading ontology:', err);
        setError('Error loading ontology');
        setLoading(false);
      }
    };

    loadOntology();
  }, []);

  const mapXSDToInputType = (xsdType: string): string => {
    switch (xsdType) {
      case 'http://www.w3.org/2001/XMLSchema#float':
      case 'http://www.w3.org/2001/XMLSchema#decimal':
      case 'http://www.w3.org/2001/XMLSchema#double':
        return 'number';
      case 'http://www.w3.org/2001/XMLSchema#dateTime':
        return 'datetime-local';
      default:
        return 'text';
    }
  };

  const handleChange = (propertyURI: string, value: string) => {
    setFormData(prev => ({ ...prev, [propertyURI]: value }));
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    // You can add further validation if needed.
    console.log("Submitted Sensor Data:", formData);
    // Process formData as needed (e.g. create RDF triples for the sensor instance)
  };

  if (loading) return <Spinner animation="border" role="status"><span className="visually-hidden">Loading ontology...</span></Spinner>;
  if (error) return <Alert variant="danger">Error: {error}</Alert>;

  return (
    <Form onSubmit={handleSubmit}>
      <h2>Add New Sensor</h2>
      {fields.map(field => (
        <Form.Group key={field.propertyURI} controlId={field.propertyURI} className="mb-3">
          <Form.Label>{field.label}:</Form.Label>
          <Form.Control
            type={mapXSDToInputType(field.xsdType)}
            onChange={(e) => handleChange(field.propertyURI, e.target.value)}
            required
          />
        </Form.Group>
      ))}
      <Button variant="primary" type="submit">Submit</Button>
    </Form>
  );
};

export default DynamicSensorForm;