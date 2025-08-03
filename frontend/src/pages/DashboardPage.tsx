import React from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import { useDashboardData } from '../hooks/useDashboardData';
import StatisticsCards from '../components/StatisticsCards';
import TemperatureChart from '../components/TemperatureChart';
import SparkApplicationsCard from '../components/SparkApplicationsCard';
import TemperatureAlertsCard from '../components/TemperatureAlertsCard';

const DashboardPage: React.FC = () => {
  const {
    averageTemperature,
    loading,
    timeRange,
    setTimeRange,
    sparkMasterStatus,
    loadingSparkStatus,
    temperatureAlerts,
    loadingAlerts
  } = useDashboardData();

  return (
    <Container className="mt-3">
      <h1>Dashboard</h1>
      
      {/* Statistics Cards (static charts) */}
      <StatisticsCards />
      
      {/* Temperature Chart */}
      <Row className="mt-4">
        <Col md={12}>
          <TemperatureChart
            data={averageTemperature}
            loading={loading}
            timeRange={timeRange}
            onTimeRangeChange={setTimeRange}
          />
        </Col>
      </Row>
      
      {/* Spark Applications */}
      <Row className="mt-4">
        <Col md={12}>
          <SparkApplicationsCard
            sparkMasterStatus={sparkMasterStatus}
            loading={loadingSparkStatus}
          />
        </Col>
      </Row>
      
      {/* Temperature Alerts */}
      <Row className="mt-4">
        <Col md={12}>
          <TemperatureAlertsCard
            alerts={temperatureAlerts}
            loading={loadingAlerts}
          />
        </Col>
      </Row>
    </Container>
  );
};

export default DashboardPage;
