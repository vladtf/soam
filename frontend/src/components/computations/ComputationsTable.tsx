import React from 'react';
import { Badge, Button } from 'react-bootstrap';
import WithTooltip from '../WithTooltip';
import ThemedTable from '../ThemedTable';
import type { ComputationDef } from '../../api/backendRequests';

interface Props {
  items: ComputationDef[];
  loading: boolean;
  onEdit: (item: ComputationDef) => void;
  onPreview: (id?: number) => void;
  onDelete: (id?: number) => void;
}

const ComputationsTable: React.FC<Props> = ({ items, loading, onEdit, onPreview, onDelete }) => {
  if (loading) return <div>Loading…</div>;
  return (
    <ThemedTable responsive hover size="sm">
      <thead>
        <tr>
          <th>Name</th>
          <th>Dataset</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {items.map((it) => (
          <tr key={it.id}>
            <td>{it.name}</td>
            <td>
              <Badge bg="secondary">{it.dataset}</Badge>
            </td>
            <td>{it.enabled ? <Badge bg="success">enabled</Badge> : <Badge bg="secondary">disabled</Badge>}</td>
            <td className="d-flex gap-2">
              <WithTooltip tip="Edit this computation">
                <Button size="sm" variant="outline-primary" onClick={() => onEdit(it)}>
                  Edit
                </Button>
              </WithTooltip>
              <WithTooltip tip="Run a quick preview to see sample results">
                <Button size="sm" variant="outline-secondary" onClick={() => onPreview(it.id)}>
                  Preview
                </Button>
              </WithTooltip>
              <WithTooltip tip="Delete this computation">
                <Button size="sm" variant="outline-danger" onClick={() => onDelete(it.id)}>
                  Delete
                </Button>
              </WithTooltip>
            </td>
          </tr>
        ))}
      </tbody>
    </ThemedTable>
  );
};

export default ComputationsTable;
