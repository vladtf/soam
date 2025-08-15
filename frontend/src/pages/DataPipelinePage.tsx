import React from 'react';
import { Container, Row, Col, Tab } from 'react-bootstrap';
import { usePipelineData } from '../hooks/usePipelineData';

// Import components
import TopControlsBar from '../components/sensor-data/TopControlsBar';
import PipelineOverview from '../components/pipeline/PipelineOverview';
import PipelineNavigationSidebar from '../components/pipeline/PipelineNavigationSidebar';
import PipelineOverviewTab from '../components/pipeline/PipelineOverviewTab';
import SensorDataTab from '../components/pipeline/SensorDataTab';
import NormalizationTab from '../components/pipeline/NormalizationTab';
import ComputationsTab from '../components/pipeline/ComputationsTab';
import DevicesTab from '../components/pipeline/DevicesTab';

const DataPipelinePage: React.FC = () => {
  const {
    // State
    activePartition,
    partitions,
    sensorData,
    devices,
    bufferSize,
    viewMode,
    ingestionId,
    name,
    description,
    computations,
    filteredRules,
    relatedComputations,
    tableColumns,
    
    // Setters
    setActivePartition,
    setBufferSize,
    setViewMode,
    setIngestionId,
    setName,
    setDescription,
    
    // Handlers
    handleDataRefresh,
    applyBufferSize,
    handleRegisterDevice,
    handleToggleDevice,
    handleDeleteDevice,
    loadPipelineData,
    renderValue,
  } = usePipelineData();

  return (
    <Container className="pt-3 pb-4">
      <Row className="mb-4">
        <Col>
          <h2>Data Processing Pipeline</h2>
          <p className="text-muted">
            Unified view of your data processing pipeline: manage sensor data, normalization rules, and computations
          </p>
        </Col>
      </Row>

      {/* Pipeline Overview */}
      <Row className="mb-4">
        <Col>
          <PipelineOverview
            activePartition={activePartition}
            partitions={partitions}
            sensorDataCount={sensorData.length}
            devicesCount={devices.length}
            rulesCount={filteredRules.length}
            computationsCount={relatedComputations.length}
            onRefresh={handleDataRefresh}
          />
        </Col>
      </Row>

      {/* Main Controls */}
      <Row className="mb-4">
        <Col>
          <TopControlsBar
            partitions={partitions}
            activePartition={activePartition}
            setActivePartition={setActivePartition}
            bufferSize={bufferSize}
            setBufferSize={setBufferSize}
            applyBufferSize={applyBufferSize}
            viewMode={viewMode}
            setViewMode={setViewMode}
          />
        </Col>
      </Row>

      {/* Tabbed Interface with Persistent Sidebar */}
      <Tab.Container defaultActiveKey="overview">
        <Row>
          <Col lg={3} xl={2}>
            {/* Persistent Navigation Sidebar */}
            <PipelineNavigationSidebar
              sensorData={sensorData}
              devices={devices}
              filteredRules={filteredRules}
              relatedComputations={relatedComputations}
            />
          </Col>
          
          <Col lg={9} xl={10}>
            <Tab.Content>
              <Tab.Pane eventKey="overview">
                <PipelineOverviewTab
                  sensorData={sensorData}
                  devices={devices}
                  filteredRules={filteredRules}
                  relatedComputations={relatedComputations}
                  computations={computations}
                  activePartition={activePartition}
                  partitions={partitions}
                  tableColumns={tableColumns}
                />
              </Tab.Pane>

              <Tab.Pane eventKey="sensors">
                <SensorDataTab
                  sensorData={sensorData}
                  activePartition={activePartition}
                  viewMode={viewMode}
                  tableColumns={tableColumns}
                  renderValue={renderValue}
                />
              </Tab.Pane>

              <Tab.Pane eventKey="normalization">
                <NormalizationTab
                  filteredRules={filteredRules}
                  activePartition={activePartition}
                  partitions={partitions}
                  onRulesChange={loadPipelineData}
                  sampleData={sensorData}
                  tableColumns={tableColumns}
                  renderValue={renderValue}
                />
              </Tab.Pane>

              <Tab.Pane eventKey="computations">
                <ComputationsTab
                  relatedComputations={relatedComputations}
                  activePartition={activePartition}
                  onComputationsChange={loadPipelineData}
                  sensorData={sensorData}
                  renderValue={renderValue}
                />
              </Tab.Pane>

              <Tab.Pane eventKey="devices">
                <DevicesTab
                  devices={devices}
                  sensorData={sensorData}
                  activePartition={activePartition}
                  ingestionId={ingestionId}
                  setIngestionId={setIngestionId}
                  name={name}
                  setName={setName}
                  description={description}
                  setDescription={setDescription}
                  onRegister={handleRegisterDevice}
                  onToggle={handleToggleDevice}
                  onDelete={handleDeleteDevice}
                  renderValue={renderValue}
                />
              </Tab.Pane>
            </Tab.Content>
          </Col>
        </Row>
      </Tab.Container>
    </Container>
  );
};

export default DataPipelinePage;
