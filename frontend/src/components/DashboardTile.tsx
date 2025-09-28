import React from 'react';
import { Card, Table } from 'react-bootstrap';
// @ts-ignore - TypeScript type declarations issue with recharts package
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { formatDisplayValue, roundNumericValue } from '../utils/numberUtils';

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
    const valueField = (config?.valueField as string) || 'avg_temperature';
    const val = data?.[0]?.[valueField];
    return (
      <Card className="shadow-sm border-body h-100 d-flex flex-column">
        <Card.Body className="d-flex flex-column justify-content-center text-center">
          <div className="text-body-secondary small mb-2">{title}</div>
          <div className="display-6" style={{ fontSize: 'clamp(1.5rem, 4vw, 3rem)' }}>{formatDisplayValue(val)}</div>
        </Card.Body>
      </Card>
    );
  }
  
  if (viz === 'timeseries') {
    const timeField = (config?.timeField as string) || 'time_start';
    const valueField = (config?.valueField as string) || 'avg_temperature';
    
    // Ensure time series data is sorted chronologically for proper chart display
    // and round ALL numeric values to 2 decimal places while keeping them as numbers
    const sortedData = data.length > 0 ? [...data].sort((a: any, b: any) => {
      const timeA = new Date(a[timeField]).getTime();
      const timeB = new Date(b[timeField]).getTime();
      return timeA - timeB; // Sort ascending (oldest to newest)
    }).map((item: any) => {
      const roundedItem: any = {};
      Object.keys(item).forEach(key => {
        roundedItem[key] = roundNumericValue(item[key]);
      });
      return roundedItem;
    }) : data;
    
    return (
      <Card className="shadow-sm border-body h-100 d-flex flex-column">
        <Card.Header className="fw-semibold flex-shrink-0">{title}</Card.Header>
        <Card.Body className="flex-grow-1 p-2 d-flex flex-column" style={{ minHeight: 0 }}>
          <div className="flex-grow-1" style={{ minHeight: 0 }}>
            {sortedData && sortedData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sortedData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey={timeField} 
                    tick={{ fontSize: 11 }}
                    label={{ value: 'Time', position: 'insideBottomRight', offset: -5, style: { textAnchor: 'end', fontSize: 11 } }}
                    tickFormatter={(value: any) => {
                      try {
                        const date = new Date(value);
                        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                      } catch {
                        return String(value);
                      }
                    }}
                  />
                  <YAxis 
                    tick={{ fontSize: 11 }} 
                    label={{ value: valueField, angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fontSize: 11 } }}
                    tickFormatter={(value: any) => formatDisplayValue(value)}
                  />
                  <Tooltip 
                    labelFormatter={(value: any) => {
                      try {
                        const date = new Date(value);
                        return date.toLocaleString();
                      } catch {
                        return String(value);
                      }
                    }}
                    formatter={(value: any, name: string) => [formatDisplayValue(value), name]}
                    content={({ active, payload, label }: any) => {
                      if (active && payload && payload.length) {
                        return (
                          <div className="bg-white border rounded shadow-sm p-2" style={{ fontSize: '12px' }}>
                            <p className="mb-1">{label}</p>
                            {payload.map((entry: any, index: number) => (
                              <p key={index} className="mb-0" style={{ color: entry.color }}>
                                {entry.dataKey} : {formatDisplayValue(entry.value)}
                              </p>
                            ))}
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey={valueField} 
                    stroke="#0d6efd" 
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, stroke: '#0d6efd', strokeWidth: 2, fill: '#fff' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="d-flex align-items-center justify-content-center h-100 text-body-secondary">
                <div className="text-center">
                  <div>No data available</div>
                  <small>Configure {timeField} and {valueField} fields</small>
                </div>
              </div>
            )}
          </div>
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
                  {columns.map((c) => (<td key={c} className="px-3 py-2">{formatDisplayValue((r as any)[c])}</td>))}
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </Card.Body>
    </Card>
  );
};
