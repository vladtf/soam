import React, { useState, useEffect } from 'react';
import { Form, Spinner, Alert } from 'react-bootstrap';
import * as rdflib from 'rdflib';
import { useError } from '../context/ErrorContext';
import { reportClientError } from '../errors';

export interface FormField {
	propertyURI: string;
	label: string;
	xsdType: string;
}

export interface DynamicFieldsProps {
	fields: FormField[];
	onFieldChange: (propertyURI: string, value: string) => void;
	depth?: number;
	dropdownOptions?: Record<string, string[]>;
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

const DynamicFields: React.FC<DynamicFieldsProps> = ({ fields, onFieldChange, depth = 0, dropdownOptions }) => (
	<div style={{ marginLeft: depth * 20 }}>
		{fields.map(field => {
			const inputType = mapXSDToInputType(field.xsdType);
			return (
				<Form.Group key={field.propertyURI} controlId={field.propertyURI} className="mb-3">
					<Form.Label>
						{depth > 0 && <span style={{ marginRight: 5 }}>└─</span>}
						{field.label} ({field.xsdType.split('#').pop()}):
					</Form.Label>
					{inputType === 'complex' ? (
						<DynamicFieldsWrapper
							classURI={field.xsdType}
							onFieldChange={onFieldChange}
							depth={depth + 1}
							dropdownOptions={depth === 0 ? dropdownOptions : undefined}
						/>
					) : (
						<>
							{depth === 0 && dropdownOptions ? (
								<Form.Select onChange={e => onFieldChange(field.propertyURI, e.target.value)} required>
									<option value="">Select {field.label}</option>
									{Object.keys(dropdownOptions).map(option => (
										<option key={option} value={option}>
											{option} ({dropdownOptions[option].toString().split('#').pop()})
										</option>
									))}
								</Form.Select>
							) : (
								<Form.Control
									type={inputType}
									onChange={e => onFieldChange(field.propertyURI, e.target.value)}
									required
								/>
							)}
						</>
					)}
				</Form.Group>
			);
		})}
	</div>
);

interface DynamicFieldsWrapperProps {
	classURI: string;
	onFieldChange: (propertyURI: string, value: string) => void;
	depth?: number;
	// Pass dropdownOptions down only at top level.
	dropdownOptions?: Record<string, string[]>;
}

export const DynamicFieldsWrapper: React.FC<DynamicFieldsWrapperProps> = ({ classURI, onFieldChange, depth = 0, dropdownOptions }) => {
	const [fields, setFields] = useState<FormField[]>([]);
	const [loading, setLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);
    const { setError: setGlobalError } = useError();

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
				setGlobalError(err instanceof Error ? err.message : (err as any));
				reportClientError({ message: String(err), severity: 'error', component: 'DynamicFields', context: 'loadOntology' }).catch(() => {});
				setError('Error loading ontology');
				setLoading(false);
			}
		};
		loadOntology();
	}, [classURI]);

	if (loading) return <Spinner animation="border" size="sm" role="status" />;
	if (error) return <Alert variant="danger">Error: {error}</Alert>;

	return <DynamicFields fields={fields} onFieldChange={onFieldChange} depth={depth} dropdownOptions={dropdownOptions} />;
};

export default DynamicFields;
