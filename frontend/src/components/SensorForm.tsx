import React, { useEffect, useState } from 'react';
import * as rdflib from 'rdflib';
import { Form, Button, Spinner, Alert } from 'react-bootstrap';
import DynamicFields, { FormField } from './DynamicFields';
import { useNavigate } from 'react-router-dom';
import { fetchBuildings } from '../api/backendRequests';

const SENSOR_CLASS = 'http://example.org/smartcity#Sensor';
const RDFS_DOMAIN = 'http://www.w3.org/2000/01/rdf-schema#domain';
const RDFS_RANGE = 'http://www.w3.org/2000/01/rdf-schema#range';
const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';

interface SensorFormProps {
	dataSchema: Record<string, string[]>;
}

const SensorForm: React.FC<SensorFormProps> = ({ dataSchema }) => {
	const [fields, setFields] = useState<FormField[]>([]);
	const [formData, setFormData] = useState<Record<string, string>>({});
	const [loading, setLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);
	const [buildings, setBuildings] = useState<{ name: string }[]>([]); // new state for buildings
	const navigate = useNavigate(); // new hook for navigation

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

	useEffect(() => {
		// Fetch buildings from backend
		fetchBuildings()
			.then((data: { name: string }[]) => setBuildings(data))
			.catch(err => console.error("Error fetching buildings:", err));
	}, []);

	const handleFieldChange = (propertyURI: string, value: string) => {
		setFormData(prev => ({ ...prev, [propertyURI]: value }));
	};

	const handleBuildingChange = (event: React.ChangeEvent<HTMLInputElement>) => {
		const selected = event.target.value;
		if (selected === 'add_new') {
			navigate('/map'); // use navigate instead of history.push
		} else {
			setFormData(prev => ({ ...prev, building: selected }));
		}
	};

	const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
		e.preventDefault();
		console.log('Submitted Sensor Data:', formData);
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
			<Form.Group controlId="buildingDropdown">
				<Form.Label>Select Building</Form.Label>
				<Form.Control as="select" onChange={handleBuildingChange} defaultValue="">
					<option value="" disabled>Select a building</option>
					{buildings.map((b, i) => (
						<option key={i} value={b.name}>{b.name}</option>
					))}
					<option value="add_new">Add new building</option>
				</Form.Control>
			</Form.Group>
			<DynamicFields
				fields={fields}
				onFieldChange={handleFieldChange}
				dropdownOptions={dataSchema}
			/>
			<Button variant="primary" type="submit">
				Submit
			</Button>
		</Form>
	);
};

export default SensorForm;
