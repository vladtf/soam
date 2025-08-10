import React from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import { useDashboardData } from '../hooks/useDashboardData';
import StatisticsCards from '../components/StatisticsCards';
import TemperatureChart from '../components/TemperatureChart';
import SparkApplicationsCard from '../components/SparkApplicationsCard';
import TemperatureAlertsCard from '../components/TemperatureAlertsCard';
import PageHeader from '../components/PageHeader';

const DashboardPage: React.FC = () => {
  const {
    averageTemperature,
    loading,
    timeRange,
    setTimeRange,
    sparkMasterStatus,
    loadingSparkStatus,
    temperatureAlerts,
  loadingAlerts,
  lastUpdated,
  autoRefresh,
  setAutoRefresh,
  refreshAll,
  } = useDashboardData();

  return (
    <Container className="pt-3 pb-4">
      <PageHeader
        title="Dashboard"
        subtitle="Overview of key metrics and cluster status"
        onRefresh={refreshAll}
        refreshing={loading || loadingSparkStatus || loadingAlerts}
        autoRefresh={autoRefresh}
        onToggleAutoRefresh={setAutoRefresh}
        lastUpdated={lastUpdated}
      />
      
      {/* Statistics Cards (static charts) */}
      <StatisticsCards />
      
      {/* Temperature Chart */}
  <Row className="g-3 mt-1">
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
  <Row className="g-3 mt-1">
        <Col md={12}>
          <SparkApplicationsCard
            sparkMasterStatus={sparkMasterStatus}
            loading={loadingSparkStatus}
          />
        </Col>
      </Row>
      
      {/* Temperature Alerts */}
  <Row className="g-3 mt-1">
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
