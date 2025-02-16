import React, { useState, useEffect } from 'react';
import { Form, Spinner, Alert } from 'react-bootstrap';
import * as rdflib from 'rdflib';

export interface FormField {
	propertyURI: string;
	label: string;
	xsdType: string;
}

export interface DynamicFieldsProps {
	fields: FormField[];
	onFieldChange: (propertyURI: string, value: string) => void;
	depth?: number;
}

export const mapXSDToInputType = (xsdType: string): string => {
	switch (xsdType) {
		case 'http://www.w3.org/2001/XMLSchema#float':
		case 'http://www.w3.org/2001/XMLSchema#decimal':
		case 'http://www.w3.org/2001/XMLSchema#double':
			return 'number';
		case 'http://www.w3.org/2001/XMLSchema#dateTime':
			return 'datetime-local';
		case 'http://www.w3.org/2001/XMLSchema#string':
			return 'text';
		default:
			return 'complex';
	}
};

const DynamicFields: React.FC<DynamicFieldsProps> = ({ fields, onFieldChange, depth = 0 }) => (
	<div style={{ marginLeft: depth * 20 }}>
		{fields.map(field => (
			<Form.Group key={field.propertyURI} controlId={field.propertyURI} className="mb-3">
				<Form.Label>
					{depth > 0 && <span style={{ marginRight: 5 }}>└─</span>}
					{field.label} ({field.xsdType.split('#').pop()}):
				</Form.Label>
				{mapXSDToInputType(field.xsdType) === 'complex' ? (
					<DynamicFieldsWrapper classURI={field.xsdType} onFieldChange={onFieldChange} depth={depth + 1} />
				) : (
					<Form.Control
						type={mapXSDToInputType(field.xsdType)}
						onChange={e => onFieldChange(field.propertyURI, e.target.value)}
						required
					/>
				)}
			</Form.Group>
		))}
	</div>
);

interface DynamicFieldsWrapperProps {
	classURI: string;
	onFieldChange: (propertyURI: string, value: string) => void;
	depth?: number;
}

export const DynamicFieldsWrapper: React.FC<DynamicFieldsWrapperProps> = ({ classURI, onFieldChange, depth = 0 }) => {
	const [fields, setFields] = useState<FormField[]>([]);
	const [loading, setLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const loadOntology = async () => {
			try {
				const store = rdflib.graph();
				const fetcher = new rdflib.Fetcher(store, { fetch: window.fetch.bind(window) });
				const owlUrl = `${window.location.origin}/ontology.owl`;
				await fetcher.load(owlUrl);

				const RDFS_DOMAIN = 'http://www.w3.org/2000/01/rdf-schema#domain';
				const RDFS_RANGE = 'http://www.w3.org/2000/01/rdf-schema#range';
				const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';

				const domainStmts = store.statementsMatching(undefined, rdflib.sym(RDFS_DOMAIN), rdflib.sym(classURI));
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
	}, [classURI]);

	if (loading) return <Spinner animation="border" size="sm" role="status" />;
	if (error) return <Alert variant="danger">Error: {error}</Alert>;

	return <DynamicFields fields={fields} onFieldChange={onFieldChange} depth={depth} />;
};

export default DynamicFields;
