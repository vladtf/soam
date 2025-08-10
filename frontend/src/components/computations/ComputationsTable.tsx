import React from 'react';
import { Table, Badge, Button } from 'react-bootstrap';
import type { ComputationDef } from '../../api/backendRequests';

interface Props {
  items: ComputationDef[];
  isDark: boolean;
  loading: boolean;
  onEdit: (item: ComputationDef) => void;
  onPreview: (id?: number) => void;
  onDelete: (id?: number) => void;
}

const ComputationsTable: React.FC<Props> = ({ items, isDark, loading, onEdit, onPreview, onDelete }) => {
  if (loading) return <div>Loading…</div>;
  return (
    <Table responsive hover size="sm" variant={isDark ? 'dark' : undefined}>
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
              <Button size="sm" variant="outline-primary" onClick={() => onEdit(it)}>
                Edit
              </Button>
              <Button size="sm" variant="outline-secondary" onClick={() => onPreview(it.id)}>
                Preview
              </Button>
              <Button size="sm" variant="outline-danger" onClick={() => onDelete(it.id)}>
                Delete
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
};

export default ComputationsTable;
