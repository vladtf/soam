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
      <Card className="shadow-sm border-body h-100 d-flex flex-column">
        <Card.Body className="d-flex flex-column justify-content-center text-center">
          <div className="text-body-secondary small mb-2">{title}</div>
          <div className="display-6" style={{ fontSize: 'clamp(1.5rem, 4vw, 3rem)' }}>{val ?? '—'}</div>
        </Card.Body>
      </Card>
    );
  }
  // default: table
  const columns = (config?.columns as string[]) || Object.keys(data?.[0] || {});
  
  return (
    <Card className="shadow-sm border-body h-100 d-flex flex-column">
      <Card.Header className="fw-semibold flex-shrink-0">{title}</Card.Header>
      <Card.Body className="flex-grow-1 p-0 d-flex flex-column" style={{ minHeight: 0 }}>
        <div className="flex-grow-1" style={{ overflow: 'auto' }}>
          <Table size="sm" responsive className="mb-0">
            <thead className="sticky-top bg-light">
              <tr>
                {columns.map((c) => (<th key={c} className="px-3 py-2 border-bottom">{c}</th>))}
              </tr>
            </thead>
            <tbody>
              {data?.map((r, idx) => (
                <tr key={idx}>
                  {columns.map((c) => (<td key={c} className="px-3 py-2">{String((r as any)[c] ?? '')}</td>))}
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </Card.Body>
    </Card>
  );
};
