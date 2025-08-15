import React from 'react';
import { Card, Spinner } from 'react-bootstrap';
import ThemedTable from '../ThemedTable';
import ThemedReactJson from '../ThemedReactJson';

export interface DataViewerProps {
    data: any[];
    viewMode: 'table' | 'json';
    tableColumns: string[];
    renderValue: (v: unknown) => string;
}

const DataViewer: React.FC<DataViewerProps> = ({ data, viewMode, tableColumns, renderValue }) => {
    return (
        <Card>
            <Card.Header className="py-2">
                <strong>Sensor Data</strong>
            </Card.Header>
            <Card.Body className="p-0">
                {viewMode === 'table' ? (
                    <div style={{ maxHeight: '70vh', overflow: 'auto' }}>
                        {data && data.length > 0 ? (
                            <ThemedTable size="sm" responsive hover className="mb-0">
                                <thead>
                                    <tr>
                                        {tableColumns.map((c) => (
                                            <th key={c}>{c}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.map((row, idx) => (
                                        <tr key={idx}>
                                            {tableColumns.map((c) => (
                                                <td key={c}>{renderValue((row as any)[c])}</td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </ThemedTable>
                        ) : (
                            <div className="d-flex align-items-center justify-content-center py-5">
                                <Spinner animation="border" role="status" className="me-2" />
                                <span className="text-muted">Waiting for data…</span>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="p-2" style={{ maxHeight: '70vh', overflow: 'auto' }}>
                        {data && data.length > 0 ? (
                            <ThemedReactJson src={data} collapsed={false} />
                        ) : (
                            <div className="d-flex align-items-center justify-content-center py-5">
                                <Spinner animation="border" role="status" className="me-2" />
                                <span className="text-muted">Waiting for data…</span>
                            </div>
                        )}
                    </div>
                )}
            </Card.Body>
        </Card>
    );
};

export default DataViewer;
