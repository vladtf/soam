import React, { useState, useEffect, useMemo } from 'react';
import { Row, Col, Card, Table, Badge, Nav, Alert, Spinner, Button, Accordion, Pagination, Form } from 'react-bootstrap';
import { 
  FaDatabase, 
  FaTable, 
  FaChartBar, 
  FaClock,
  FaInfoCircle,
  FaFile,
  FaBug,
  FaServer,
  FaSyncAlt
} from 'react-icons/fa';
import { 
  getIngestorMetadataStats, 
  getIngestorDatasets, 
  getIngestorTopicsSummary,
  DatasetMetadata,
  TopicSummary,
  MetadataStats
} from '../api/backendRequests';
import { useTheme } from '../context/ThemeContext';
import { extractErrorMessage } from '../utils/errorHandling';
import { logger } from '../utils/logger';

interface MetadataViewerProps {
  className?: string;
}

const MetadataViewer: React.FC<MetadataViewerProps> = ({ className }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<MetadataStats | null>(null);
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [topics, setTopics] = useState<TopicSummary[]>([]);
  const [activeTab, setActiveTab] = useState('datasets');
  
  // Pagination for datasets
  const [datasetCurrentPage, setDatasetCurrentPage] = useState(1);
  const [datasetItemsPerPage, setDatasetItemsPerPage] = useState(5);

  useEffect(() => {
    loadMetadata();
  }, []);

  // Reset pagination when datasets change or when switching to datasets tab
  useEffect(() => {
    setDatasetCurrentPage(1);
  }, [datasets.length, activeTab]);

  const loadMetadata = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [statsData, datasetsData, topicsData] = await Promise.all([
        getIngestorMetadataStats(),
        getIngestorDatasets(),
        getIngestorTopicsSummary()
      ]);

      setStats(statsData);
      setDatasets(datasetsData);
      setTopics(topicsData);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to load metadata'));
      logger.error('MetadataViewer', 'Failed to load metadata', err);
    } finally {
      setLoading(false);
    }
  };

  // Calculate paginated datasets
  const paginatedDatasets = useMemo(() => {
    if (datasetItemsPerPage === -1) {
      // Show all datasets
      return {
        datasets: datasets,
        totalPages: 1,
        totalDatasets: datasets.length
      };
    }
    
    const startIndex = (datasetCurrentPage - 1) * datasetItemsPerPage;
    const endIndex = startIndex + datasetItemsPerPage;
    
    return {
      datasets: datasets.slice(startIndex, endIndex),
      totalPages: Math.ceil(datasets.length / datasetItemsPerPage),
      totalDatasets: datasets.length
    };
  }, [datasets, datasetCurrentPage, datasetItemsPerPage]);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDateTime = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  };

  const getSchemaTypeBadgeVariant = (type: string) => {
    const variants: Record<string, string> = {
      string: 'primary',
      integer: 'success',
      double: 'warning',
      boolean: 'secondary',
      timestamp: 'info',
      uuid: isDark ? 'secondary' : 'light',
      array: 'danger',
      object: isDark ? 'light' : 'dark',
      null: 'outline-secondary'
    };
    return variants[type] || 'outline-secondary';
  };

  if (loading) {
    return (
      <div className={`${className} text-center py-5`}>
        <div className="d-flex flex-column align-items-center">
          <Spinner animation="border" variant="primary" className="mb-3" />
          <h5 className="text-muted">Loading metadata...</h5>
          <p className="text-muted small mb-0">Fetching datasets, schemas, and statistics</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={className}>
        <Alert variant="danger" className="border-0 shadow-sm">
          <div className="d-flex align-items-center mb-3">
            <FaDatabase className="me-2 text-danger" size="1.5rem" />
            <Alert.Heading className="mb-0">Failed to Load Metadata</Alert.Heading>
          </div>
          <p className="mb-3">{error}</p>
          <hr />
          <div className="d-flex gap-2">
            <Button variant="outline-danger" onClick={loadMetadata} disabled={loading}>
              <FaSyncAlt className={`me-1 ${loading ? 'fa-spin' : ''}`} />
              {loading ? 'Retrying...' : 'Retry'}
            </Button>
          </div>
        </Alert>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Header Section */}
      <div className={`d-flex justify-content-between align-items-center mb-4 p-3 rounded ${isDark ? 'bg-dark border' : 'bg-light'}`}>
        <div>
          <h3 className="mb-1">
            <FaDatabase className="me-2 text-primary" />
            Ingestion Metadata
          </h3>
          <p className="text-muted mb-0">Monitor data ingestion, schemas, and quality metrics</p>
        </div>
        <Button variant="outline-primary" onClick={loadMetadata} disabled={loading}>
          <FaSyncAlt className={`me-1 ${loading ? 'fa-spin' : ''}`} />
          Refresh
        </Button>
      </div>
      
      {/* Overview Statistics */}
      {stats && (
        <Row className="mb-4 g-3">
          <Col xl={2} lg={3} md={4} sm={6}>
            <Card className="text-center h-100 border-0 shadow-sm">
              <Card.Body>
                <FaTable className="mb-2" style={{ fontSize: '2.5rem', color: '#6c757d' }} />
                <Card.Title className="h4">{stats.dataset_count}</Card.Title>
                <Card.Text className="text-muted small">Datasets</Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col xl={2} lg={3} md={4} sm={6}>
            <Card className="text-center h-100 border-0 shadow-sm">
              <Card.Body>
                <FaBug className="mb-2" style={{ fontSize: '2.5rem', color: '#6c757d' }} />
                <Card.Title className="h4">{stats.topic_count}</Card.Title>
                <Card.Text className="text-muted small">Topics</Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col xl={2} lg={3} md={4} sm={6}>
            <Card className="text-center h-100 border-0 shadow-sm">
              <Card.Body>
                <FaChartBar className="mb-2" style={{ fontSize: '2.5rem', color: '#28a745' }} />
                <Card.Title className="h4">{stats.active_datasets}</Card.Title>
                <Card.Text className="text-muted small">Active</Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col xl={2} lg={3} md={4} sm={6}>
            <Card className="text-center h-100 border-0 shadow-sm">
              <Card.Body>
                <FaServer className="mb-2" style={{ fontSize: '2.5rem', color: '#17a2b8' }} />
                <Card.Title className="h4">{stats.total_records.toLocaleString()}</Card.Title>
                <Card.Text className="text-muted small">Records</Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col xl={2} lg={3} md={4} sm={6}>
            <Card className="text-center h-100 border-0 shadow-sm">
              <Card.Body>
                <FaFile className="mb-2" style={{ fontSize: '2.5rem', color: '#fd7e14' }} />
                <Card.Title className="h4">{stats.size_mb} MB</Card.Title>
                <Card.Text className="text-muted small">Data Size</Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col xl={2} lg={3} md={4} sm={6}>
            <Card className="text-center h-100 border-0 shadow-sm">
              <Card.Body>
                <FaInfoCircle className="mb-2" style={{ fontSize: '2.5rem', color: '#e83e8c' }} />
                <Card.Title className="h4">{stats.total_unique_sensors}</Card.Title>
                <Card.Text className="text-muted small">Sensors</Card.Text>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      {/* Navigation Tabs */}
      <Card className="mb-4 border-0 shadow-sm">
        <Card.Header className={`border-bottom ${isDark ? 'bg-dark' : 'bg-white'}`}>
          <Nav variant="pills" className="justify-content-center">
            <Nav.Item>
              <Nav.Link 
                active={activeTab === 'datasets'} 
                onClick={() => setActiveTab('datasets')}
                className="px-4"
              >
                <FaDatabase className="me-2" />
                Datasets ({datasets.length})
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link 
                active={activeTab === 'topics'} 
                onClick={() => setActiveTab('topics')}
                className="px-4"
              >
                <FaBug className="me-2" />
                Topics ({topics.length})
              </Nav.Link>
            </Nav.Item>
          </Nav>
        </Card.Header>

        <Card.Body className="p-4">
          {/* Datasets Tab */}
          {activeTab === 'datasets' && (
            <div>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div className="d-flex align-items-center gap-3">
                  <h5 className="mb-0">
                    <FaDatabase className="me-2 text-primary" />
                    Dataset Details
                  </h5>
                  <Badge bg="secondary" className="fs-6">{datasets.length} datasets</Badge>
                </div>
                <div className="d-flex align-items-center gap-3">
                  {datasets.length > 5 && (
                    <div className="d-flex align-items-center gap-2">
                      <small className="text-muted">Items per page:</small>
                      <Form.Select
                        size="sm"
                        style={{ width: 'auto' }}
                        value={datasetItemsPerPage}
                        onChange={(e) => {
                          const newItemsPerPage = parseInt(e.target.value);
                          setDatasetItemsPerPage(newItemsPerPage);
                          setDatasetCurrentPage(1); // Reset to first page when changing items per page
                        }}
                      >
                        <option value={5}>5</option>
                        <option value={10}>10</option>
                        <option value={20}>20</option>
                        <option value={-1}>All</option>
                      </Form.Select>
                    </div>
                  )}
                  {datasets.length > datasetItemsPerPage && datasetItemsPerPage !== -1 && (
                    <small className="text-muted">
                      Showing {((datasetCurrentPage - 1) * datasetItemsPerPage) + 1}-{Math.min(datasetCurrentPage * datasetItemsPerPage, paginatedDatasets.totalDatasets)} of {paginatedDatasets.totalDatasets} datasets
                    </small>
                  )}
                </div>
              </div>
              
              {datasets.length === 0 ? (
                <Alert variant="info" className="text-center">
                  <FaDatabase size="3rem" className="mb-3 text-muted" />
                  <h5>No Datasets Found</h5>
                  <p className="mb-0">No ingestion data has been processed yet. Start the simulators to see metadata appear here.</p>
                </Alert>
              ) : (
                <>
                  <Accordion flush>
                    {paginatedDatasets.datasets.map((dataset, index) => (
                      <Accordion.Item key={dataset.ingestion_id} eventKey={index.toString()} className="border rounded mb-2">
                        <Accordion.Header>
                          <div className="w-100 d-flex justify-content-between align-items-center me-3">
                            <div>
                              <strong className="text-primary">{dataset.ingestion_id}</strong>
                              <Badge bg="primary" className="ms-2">{dataset.topic}</Badge>
                            </div>
                            <div className="d-flex gap-3 text-muted">
                              <small><strong>{dataset.record_count.toLocaleString()}</strong> records</small>
                              <small><strong>{dataset.unique_sensor_count}</strong> sensors</small>
                              <small><strong>{formatBytes(dataset.data_size_bytes)}</strong></small>
                            </div>
                          </div>
                        </Accordion.Header>
                      <Accordion.Body className={isDark ? 'bg-dark' : 'bg-light'}>
                        {/* Dataset Details */}
                        <Row className="mb-4 g-3">
                          <Col md={4}>
                            <Card className="border-0 shadow-sm h-100">
                              <Card.Body className="text-center">
                                <FaClock className="mb-2 text-info" style={{ fontSize: '1.5rem' }} />
                                <Card.Title className="h6">First Seen</Card.Title>
                                <Card.Text className="small text-muted">{formatDateTime(dataset.first_seen)}</Card.Text>
                              </Card.Body>
                            </Card>
                          </Col>
                          <Col md={4}>
                            <Card className="border-0 shadow-sm h-100">
                              <Card.Body className="text-center">
                                <FaClock className="mb-2 text-success" style={{ fontSize: '1.5rem' }} />
                                <Card.Title className="h6">Last Seen</Card.Title>
                                <Card.Text className="small text-muted">{formatDateTime(dataset.last_seen)}</Card.Text>
                              </Card.Body>
                            </Card>
                          </Col>
                          <Col md={4}>
                            <Card className="border-0 shadow-sm h-100">
                              <Card.Body className="text-center">
                                <FaTable className="mb-2 text-warning" style={{ fontSize: '1.5rem' }} />
                                <Card.Title className="h6">Schema Fields</Card.Title>
                                <Card.Text className="small text-muted">{dataset.schema_fields.length} fields</Card.Text>
                              </Card.Body>
                            </Card>
                          </Col>
                        </Row>

                        {/* Schema Table */}
                        <div className="mb-3">
                          <h6 className="d-flex align-items-center mb-3">
                            <FaTable className="me-2 text-primary" />
                            Schema ({dataset.schema_fields.length} fields)
                          </h6>
                          <div className="table-responsive">
                            <Table striped hover size="sm" className="mb-0">
                              <thead className={isDark ? '' : 'table-dark'}>
                                <tr>
                                  <th>Field Name</th>
                                  <th>Type</th>
                                  <th>Nullable</th>
                                  <th>Sample Values</th>
                                </tr>
                              </thead>
                              <tbody>
                                {dataset.schema_fields.map((field, idx) => (
                                  <tr key={idx}>
                                    <td><code className="text-primary">{field.name}</code></td>
                                    <td>
                                      <Badge bg={getSchemaTypeBadgeVariant(field.type)}>
                                        {field.type}
                                      </Badge>
                                    </td>
                                    <td>
                                      <Badge bg={field.nullable ? 'success' : 'danger'}>
                                        {field.nullable ? 'Yes' : 'No'}
                                      </Badge>
                                    </td>
                                    <td>
                                      <div className="d-flex flex-column gap-1">
                                        {field.sample_values?.slice(0, 3).map((sample, sampleIdx) => (
                                          <small key={sampleIdx} className="text-muted font-monospace">
                                            {String(sample).length > 50 ? String(sample).substring(0, 50) + '...' : String(sample)}
                                          </small>
                                        ))}
                                        {(field.sample_values?.length || 0) > 3 && (
                                          <small className="text-muted fst-italic">
                                            ... +{(field.sample_values?.length || 0) - 3} more
                                          </small>
                                        )}
                                      </div>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </Table>
                          </div>
                        </div>
                      </Accordion.Body>
                    </Accordion.Item>
                  ))}
                </Accordion>
                
                {/* Pagination */}
                {paginatedDatasets.totalPages > 1 && datasetItemsPerPage !== -1 && (
                  <div className="d-flex justify-content-center mt-4">
                    <Pagination size="sm">
                      <Pagination.First 
                        onClick={() => setDatasetCurrentPage(1)}
                        disabled={datasetCurrentPage === 1}
                      />
                      <Pagination.Prev 
                        onClick={() => setDatasetCurrentPage(prev => Math.max(1, prev - 1))}
                        disabled={datasetCurrentPage === 1}
                      />
                      
                      {/* Show page numbers */}
                      {Array.from({ length: Math.min(5, paginatedDatasets.totalPages) }, (_, i) => {
                        let pageNum;
                        if (paginatedDatasets.totalPages <= 5) {
                          pageNum = i + 1;
                        } else if (datasetCurrentPage <= 3) {
                          pageNum = i + 1;
                        } else if (datasetCurrentPage >= paginatedDatasets.totalPages - 2) {
                          pageNum = paginatedDatasets.totalPages - 4 + i;
                        } else {
                          pageNum = datasetCurrentPage - 2 + i;
                        }
                        
                        return (
                          <Pagination.Item
                            key={pageNum}
                            active={pageNum === datasetCurrentPage}
                            onClick={() => setDatasetCurrentPage(pageNum)}
                          >
                            {pageNum}
                          </Pagination.Item>
                        );
                      })}
                      
                      <Pagination.Next 
                        onClick={() => setDatasetCurrentPage(prev => Math.min(paginatedDatasets.totalPages, prev + 1))}
                        disabled={datasetCurrentPage === paginatedDatasets.totalPages}
                      />
                      <Pagination.Last 
                        onClick={() => setDatasetCurrentPage(paginatedDatasets.totalPages)}
                        disabled={datasetCurrentPage === paginatedDatasets.totalPages}
                      />
                    </Pagination>
                  </div>
                )}
                </>
              )}
            </div>
          )}
          {activeTab === 'topics' && (
            <div>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 className="mb-0">
                  <FaBug className="me-2 text-primary" />
                  Topic Summary
                </h5>
                <Badge bg="secondary" className="fs-6">{topics.length} topics</Badge>
              </div>
              
              {topics.length === 0 ? (
                <Alert variant="info" className="text-center">
                  <FaBug size="3rem" className="mb-3 text-muted" />
                  <h5>No Topics Found</h5>
                  <p className="mb-0">No MQTT topics have been detected yet. Start the simulators to see topic data appear here.</p>
                </Alert>
              ) : (
                <div className="table-responsive">
                  <Table striped hover className="mb-0">
                    <thead className={isDark ? '' : 'table-dark'}>
                      <tr>
                        <th>Topic</th>
                        <th>Datasets</th>
                        <th>Total Records</th>
                        <th>Total Size</th>
                        <th>Unique Sensors</th>
                        <th>Latest Data</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topics.map((topic, index) => (
                        <tr key={index}>
                          <td>
                            <Badge bg="primary" className="font-monospace">{topic.topic}</Badge>
                          </td>
                          <td><Badge bg="secondary">{topic.dataset_count}</Badge></td>
                          <td className="text-end">{topic.total_records.toLocaleString()}</td>
                          <td className="text-end">{formatBytes(topic.total_size_bytes)}</td>
                          <td className="text-center">
                            <Badge bg="info">{topic.total_unique_sensors}</Badge>
                          </td>
                          <td className="font-monospace small">{formatDateTime(topic.latest_data)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              )}
            </div>
          )}
        </Card.Body>
      </Card>
    </div>
  );
};

export default MetadataViewer;
