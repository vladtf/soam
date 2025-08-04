import React, { useState, useEffect } from 'react';
import { Container, Form, Button, Alert, Card, Table, Badge, Spinner } from 'react-bootstrap';
import { submitFeedback, fetchFeedbacks, FeedbackData, FeedbackResponse } from '../api/backendRequests';

const FeedbackPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [feedback, setFeedback] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Feedback list state
  const [feedbacks, setFeedbacks] = useState<FeedbackResponse[]>([]);
  const [feedbacksLoading, setFeedbacksLoading] = useState(false);
  const [feedbacksError, setFeedbacksError] = useState<string | null>(null);

  const loadFeedbacks = async () => {
    try {
      setFeedbacksLoading(true);
      setFeedbacksError(null);
      const data = await fetchFeedbacks();
      setFeedbacks(data);
    } catch (err) {
      setFeedbacksError(err instanceof Error ? err.message : 'Failed to load feedbacks');
    } finally {
      setFeedbacksLoading(false);
    }
  };

  useEffect(() => {
    loadFeedbacks();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    try {
      const feedbackData: FeedbackData = {
        email,
        message: feedback
      };
      
      await submitFeedback(feedbackData);
      
      setSubmitted(true);
      setEmail('');
      setFeedback('');
      
      // Reload feedbacks to show the new submission
      await loadFeedbacks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit feedback');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  const getEmailBadgeVariant = (email: string) => {
    // Simple hash to determine badge color based on email
    const hash = email.split('').reduce((a, b) => {
      a = ((a << 5) - a) + b.charCodeAt(0);
      return a & a;
    }, 0);
    
    const variants = ['primary', 'secondary', 'success', 'info', 'warning'];
    return variants[Math.abs(hash) % variants.length];
  };

  return (
    <Container className="mt-4">
      <h1>Feedback / Bug Report</h1>
      
      {/* Feedback Form */}
      <Card className="mb-4">
        <Card.Header>
          <h5 className="mb-0">Submit New Feedback</h5>
        </Card.Header>
        <Card.Body>
          {submitted && <Alert variant="success">Feedback submitted successfully!</Alert>}
          {error && <Alert variant="danger">{error}</Alert>}
          <Form onSubmit={handleSubmit}>
            <Form.Group controlId="feedbackEmail" className="mb-3">
              <Form.Label>Email address</Form.Label>
              <Form.Control 
                type="email" 
                placeholder="Enter your email" 
                value={email} 
                onChange={(e) => setEmail(e.target.value)} 
                required 
                disabled={loading}
              />
            </Form.Group>
            <Form.Group controlId="feedbackMessage" className="mb-3">
              <Form.Label>Feedback / Bug Description</Form.Label>
              <Form.Control 
                as="textarea" 
                rows={5} 
                placeholder="Describe your feedback or bug here" 
                value={feedback} 
                onChange={(e) => setFeedback(e.target.value)} 
                required 
                disabled={loading}
              />
            </Form.Group>
            <Button variant="primary" type="submit" disabled={loading}>
              {loading ? 'Submitting...' : 'Submit Feedback'}
            </Button>
          </Form>
        </Card.Body>
      </Card>

      {/* Feedback List */}
      <Card>
        <Card.Header className="d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Previous Feedback Submissions</h5>
          <Button 
            variant="outline-primary" 
            size="sm" 
            onClick={loadFeedbacks}
            disabled={feedbacksLoading}
          >
            {feedbacksLoading ? 'Loading...' : 'Refresh'}
          </Button>
        </Card.Header>
        <Card.Body>
          {feedbacksError && (
            <Alert variant="danger" className="mb-3">
              {feedbacksError}
            </Alert>
          )}
          
          {feedbacksLoading ? (
            <div className="text-center py-4">
              <Spinner animation="border" role="status">
                <span className="visually-hidden">Loading...</span>
              </Spinner>
              <p className="mt-2">Loading feedback submissions...</p>
            </div>
          ) : feedbacks.length === 0 ? (
            <div className="text-center py-4">
              <h6>No feedback submitted yet</h6>
              <p className="text-muted mb-0">
                Submitted feedback will appear here.
              </p>
            </div>
          ) : (
            <>
              <p className="text-muted mb-3">
                Total submissions: <strong>{feedbacks.length}</strong>
              </p>
              <Table striped hover responsive>
                <thead>
                  <tr>
                    <th style={{ width: '80px' }}>ID</th>
                    <th style={{ width: '200px' }}>Email</th>
                    <th style={{ width: '180px' }}>Submitted</th>
                    <th>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {feedbacks.map((feedbackItem) => (
                    <tr key={feedbackItem.id}>
                      <td>
                        <Badge bg="light" text="dark">
                          #{feedbackItem.id}
                        </Badge>
                      </td>
                      <td>
                        <Badge bg={getEmailBadgeVariant(feedbackItem.email)}>
                          {feedbackItem.email}
                        </Badge>
                      </td>
                      <td>
                        <small className="text-muted">
                          {formatDate(feedbackItem.created_at)}
                        </small>
                      </td>
                      <td>
                        <div style={{ 
                          maxWidth: '400px', 
                          wordWrap: 'break-word',
                          whiteSpace: 'pre-wrap'
                        }}>
                          {feedbackItem.message}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </>
          )}
        </Card.Body>
      </Card>
    </Container>
  );
};

export default FeedbackPage;
