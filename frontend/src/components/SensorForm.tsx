import React, { useEffect, useState } from 'react';
import * as rdflib from 'rdflib';
import { Form, Button, Spinner, Alert } from 'react-bootstrap';
import DynamicFields, { FormField } from './DynamicFields';

const SENSOR_CLASS = 'http://example.org/smartcity#Sensor';
const RDFS_DOMAIN = 'http://www.w3.org/2000/01/rdf-schema#domain';
const RDFS_RANGE = 'http://www.w3.org/2000/01/rdf-schema#range';
const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';

const SensorForm: React.FC = () => {
	const [fields, setFields] = useState<FormField[]>([]);
	const [formData, setFormData] = useState<{ [propertyURI: string]: string }>({});
	const [loading, setLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const loadOntology = async () => {
			try {
				const store = rdflib.graph();
				const fetcher = new rdflib.Fetcher(store, { fetch: window.fetch.bind(window) });
				const owlUrl = `${window.location.origin}/ontology.owl`;
				await fetcher.load(owlUrl);

				const domainStmts = store.statementsMatching(undefined, rdflib.sym(RDFS_DOMAIN), rdflib.sym(SENSOR_CLASS));
				const extractedFields: FormField[] = [];

				domainStmts.forEach(stmt => {
					const propertyURI = stmt.subject.value;
					const labelNode = store.any(rdflib.sym(propertyURI), rdflib.sym(RDFS_LABEL));
					const label = labelNode ? labelNode.value : propertyURI;
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

	const handleFieldChange = (propertyURI: string, value: string) => {
		setFormData(prev => ({ ...prev, [propertyURI]: value }));
	};

	const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
		e.preventDefault();
		console.log('Submitted Sensor Data:', formData);
		// Process formData as needed
	};

	if (loading)
		return (
			<Spinner animation="border" role="status">
				<span className="visually-hidden">Loading ontology...</span>
			</Spinner>
		);
	if (error) return <Alert variant="danger">Error: {error}</Alert>;

	return (
		<Form onSubmit={handleSubmit}>
			<h2>Add New Sensor</h2>
			<DynamicFields fields={fields} onFieldChange={handleFieldChange} />
			<Button variant="primary" type="submit">
				Submit
			</Button>
		</Form>
	);
};

export default SensorForm;
