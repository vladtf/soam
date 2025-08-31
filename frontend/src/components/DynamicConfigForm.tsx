import React from 'react';
import { Form } from 'react-bootstrap';
import { JsonSchema, JsonSchemaProperty } from '../types/dataSource';

interface DynamicConfigFormProps {
  schema: JsonSchema;
  value: Record<string, any>;
  onChange: (value: Record<string, any>) => void;
}

const DynamicConfigForm: React.FC<DynamicConfigFormProps> = ({ schema, value, onChange }) => {
  const handleInputChange = (key: string, inputValue: any) => {
    onChange({
      ...value,
      [key]: inputValue
    });
  };

  const renderField = (key: string, property: JsonSchemaProperty, isRequired: boolean = false) => {
    const currentValue = value[key] ?? property.default ?? '';

    switch (property.type) {
      case 'string':
        if (property.enum) {
          // Dropdown for enum values
          return (
            <Form.Select
              value={currentValue}
              onChange={(e) => handleInputChange(key, e.target.value)}
              required={isRequired}
            >
              <option value="">Select {key}...</option>
              {property.enum.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Form.Select>
          );
        } else {
          // Text input
          return (
            <Form.Control
              type={property.format === 'uri' ? 'url' : 'text'}
              placeholder={property.description || `Enter ${key}`}
              value={currentValue}
              onChange={(e) => handleInputChange(key, e.target.value)}
              required={isRequired}
            />
          );
        }

      case 'integer':
      case 'number':
        return (
          <Form.Control
            type="number"
            placeholder={property.description || `Enter ${key}`}
            value={currentValue}
            min={property.minimum}
            max={property.maximum}
            onChange={(e) => handleInputChange(key, property.type === 'integer' ? parseInt(e.target.value) || 0 : parseFloat(e.target.value) || 0)}
            required={isRequired}
          />
        );

      case 'boolean':
        return (
          <Form.Check
            type="checkbox"
            label={property.description || key}
            checked={currentValue}
            onChange={(e) => handleInputChange(key, e.target.checked)}
          />
        );

      case 'array':
        if (property.items?.type === 'string') {
          // Simple string array - use textarea with one item per line
          const arrayValue = Array.isArray(currentValue) ? currentValue.join('\n') : '';
          return (
            <Form.Control
              as="textarea"
              rows={3}
              placeholder={`Enter ${key} (one per line)`}
              value={arrayValue}
              onChange={(e) => {
                const lines = e.target.value.split('\n').filter(line => line.trim());
                handleInputChange(key, lines);
              }}
              required={isRequired}
            />
          );
        }
        break;

      case 'object':
        // Handle simple object as JSON text area
        return (
          <Form.Control
            as="textarea"
            rows={4}
            placeholder={`Enter ${key} as JSON`}
            value={typeof currentValue === 'object' ? JSON.stringify(currentValue, null, 2) : currentValue}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                handleInputChange(key, parsed);
              } catch {
                // Keep the text value for now
                handleInputChange(key, e.target.value);
              }
            }}
            required={isRequired}
          />
        );

      default:
        // Fallback to text input
        return (
          <Form.Control
            type="text"
            placeholder={property.description || `Enter ${key}`}
            value={currentValue}
            onChange={(e) => handleInputChange(key, e.target.value)}
            required={isRequired}
          />
        );
    }
  };

  const renderOneOfField = (key: string, property: JsonSchemaProperty, isRequired: boolean = false) => {
    if (!property.oneOf) return null;

    // For oneOf with string and array, show both options
    const hasStringOption = property.oneOf.some(option => option.type === 'string');
    const hasArrayOption = property.oneOf.some(option => option.type === 'array');

    if (hasStringOption && hasArrayOption) {
      const isArray = Array.isArray(value[key]);
      
      return (
        <div>
          <Form.Check
            type="radio"
            id={`${key}-single`}
            name={`${key}-type`}
            label="Single value"
            checked={!isArray}
            onChange={() => {
              if (isArray) {
                handleInputChange(key, Array.isArray(value[key]) ? value[key][0] || '' : '');
              }
            }}
          />
          <Form.Check
            type="radio"
            id={`${key}-multiple`}
            name={`${key}-type`}
            label="Multiple values"
            checked={isArray}
            onChange={() => {
              if (!isArray) {
                handleInputChange(key, [value[key] || '']);
              }
            }}
          />
          
          <div className="mt-2">
            {isArray ? (
              renderField(key, { type: 'array', items: { type: 'string' } }, isRequired)
            ) : (
              renderField(key, { type: 'string' }, isRequired)
            )}
          </div>
        </div>
      );
    }

    // Fallback to first option
    return renderField(key, property.oneOf[0], isRequired);
  };

  if (!schema.properties) {
    return <div className="text-muted">No configuration required</div>;
  }

  const requiredFields = schema.required || [];

  return (
    <div>
      {Object.entries(schema.properties).map(([key, property]) => {
        const isRequired = requiredFields.includes(key);
        
        return (
          <Form.Group key={key} className="mb-3">
            <Form.Label>
              {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              {isRequired && <span className="text-danger"> *</span>}
            </Form.Label>
            
            {property.oneOf ? (
              renderOneOfField(key, property, isRequired)
            ) : (
              renderField(key, property, isRequired)
            )}
            
            {property.description && (
              <Form.Text className="text-muted">
                {property.description}
              </Form.Text>
            )}
          </Form.Group>
        );
      })}
    </div>
  );
};

export default DynamicConfigForm;
