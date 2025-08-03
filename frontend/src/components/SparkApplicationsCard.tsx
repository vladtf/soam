import React from 'react';
import { Card, Table } from 'react-bootstrap';
import { FaTasks } from 'react-icons/fa';
import { SparkMasterStatus, SparkApplication } from '../api/backendRequests';

interface SparkApplicationsCardProps {
  sparkMasterStatus: SparkMasterStatus | null;
  loading: boolean;
}

const SparkApplicationsCard: React.FC<SparkApplicationsCardProps> = ({ 
  sparkMasterStatus, 
  loading 
}) => {
  return (
    <Card className="mb-3">
      <Card.Body>
        <Card.Title>
          <FaTasks className="me-2" /> Spark Applications
        </Card.Title>
        {loading ? (
          <div>Loading...</div>
        ) : sparkMasterStatus?.activeapps && sparkMasterStatus.activeapps.length > 0 ? (
          <Table striped bordered hover>
            <thead>
              <tr>
                <th>App Name</th>
                <th>App ID</th>
                <th>User</th>
                <th>State</th>
                <th>Cores</th>
                <th>Submit Date</th>
              </tr>
            </thead>
            <tbody>
              {sparkMasterStatus.activeapps.map((app: SparkApplication, index: number) => (
                <tr key={index}>
                  <td>{app.name}</td>
                  <td>{app.id}</td>
                  <td>{app.user}</td>
                  <td>{app.state}</td>
                  <td>{app.cores}</td>
                  <td>{app.submitdate}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <div>No active applications found.</div>
        )}
        
        {/* Show Spark Master Information */}
        {sparkMasterStatus && (
          <div className="mt-3">
            <h6>Cluster Status:</h6>
            <p><strong>Master URL:</strong> {sparkMasterStatus.url}</p>
            <p><strong>Workers:</strong> {sparkMasterStatus.aliveworkers} alive</p>
            <p><strong>Cores:</strong> {sparkMasterStatus.coresused}/{sparkMasterStatus.cores} used</p>
            <p><strong>Memory:</strong> {Math.round(sparkMasterStatus.memoryused / 1024)}MB/{Math.round(sparkMasterStatus.memory / 1024)}MB used</p>
            <p><strong>Status:</strong> {sparkMasterStatus.status}</p>
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default SparkApplicationsCard;
