import React from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import { useDashboardData } from '../hooks/useDashboardData';
import SparkApplicationsCard from '../components/SparkApplicationsCard';
import PageHeader from '../components/PageHeader';
import EnrichmentStatusCard from '../components/EnrichmentStatusCard';

const MonitoringPage: React.FC = () => {
  const {
    loading,
    sparkMasterStatus,
    loadingSparkStatus,
    refreshingSparkStatus,
    sparkStreamsStatus,
    lastUpdated,
    autoRefresh,
    setAutoRefresh,
    refreshAll,
  } = useDashboardData();

  return (
    <Container className="pt-3 pb-4">
      <PageHeader
        title="System Monitoring"
        subtitle="Spark cluster status, streaming jobs, and data enrichment health"
        onRefresh={refreshAll}
        refreshing={loading || loadingSparkStatus || refreshingSparkStatus}
        autoRefresh={autoRefresh}
        onToggleAutoRefresh={setAutoRefresh}
        lastUpdated={lastUpdated}
      />

      {/* Spark Applications & Cluster Status */}
      <Row className="g-3 mt-1">
        <Col md={12}>
          <SparkApplicationsCard
            sparkMasterStatus={sparkMasterStatus}
            sparkStreamsStatus={sparkStreamsStatus}
            loading={loadingSparkStatus}
            refreshing={refreshingSparkStatus}
            lastUpdated={lastUpdated}
          />
        </Col>
      </Row>

      {/* Enrichment Status */}
      <Row className="g-3 mt-1">
        <Col md={12}>
          <EnrichmentStatusCard 
            minutes={10} 
            autoRefresh={autoRefresh}
            refreshInterval={30000}
          />
        </Col>
      </Row>
    </Container>
  );
};

export default MonitoringPage;
