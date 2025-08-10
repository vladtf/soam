import React from 'react';
import { Card, Table } from 'react-bootstrap';

export type VizType = 'table' | 'stat' | 'timeseries';

export interface DashboardTileModel {
  id?: number;
  name: string;
  computation_id: number;
  viz_type: VizType;
  config: Record<string, unknown>;
  layout?: Record<string, unknown> | null;
  enabled?: boolean;
}

export const DashboardTile: React.FC<{ title: string; viz: VizType; data: any[]; config?: Record<string, unknown> }>
  = ({ title, viz, data, config }) => {
  if (viz === 'stat') {
    const valueField = (config?.valueField as string) || Object.keys(data?.[0] || {})[1];
    const val = data?.[0]?.[valueField];
    return (
      <Card className="shadow-sm border-body">
        <Card.Body>
          <div className="text-body-secondary small">{title}</div>
          <div className="display-6">{val ?? '—'}</div>
        </Card.Body>
      </Card>
    );
  }
  // default: table
  const columns = (config?.columns as string[]) || Object.keys(data?.[0] || {});
  return (
    <Card className="shadow-sm border-body">
      <Card.Header className="fw-semibold">{title}</Card.Header>
      <Card.Body>
        <div style={{ maxHeight: 300, overflow: 'auto' }}>
          <Table size="sm" responsive>
            <thead>
              <tr>
                {columns.map((c) => (<th key={c}>{c}</th>))}
              </tr>
            </thead>
            <tbody>
              {data?.map((r, idx) => (
                <tr key={idx}>
                  {columns.map((c) => (<td key={c}>{String((r as any)[c] ?? '')}</td>))}
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </Card.Body>
    </Card>
  );
};
