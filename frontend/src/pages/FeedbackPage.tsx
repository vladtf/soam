import React, { useState, useEffect, useMemo } from 'react';
import { Container, Form, Button, Alert, Card, Badge, Spinner } from 'react-bootstrap';
import { submitFeedback, fetchFeedbacks, FeedbackData, FeedbackResponse } from '../api/backendRequests';
import ThemedTable from '../components/ThemedTable';

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MESSAGE_MIN = 10;
const MESSAGE_MAX = 2000;
const MESSAGE_MAX_LINES = 50;

const FeedbackPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [feedback, setFeedback] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // validation state
  const [emailError, setEmailError] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

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

  // reset success banner when user edits again
  useEffect(() => {
    if (submitted) setSubmitted(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email, feedback]);

  // ---- validation helpers ----
  const validateEmail = (value: string): string | null => {
    const v = value.trim();
    if (!v) return 'Email is required.';
    if (!EMAIL_REGEX.test(v)) return 'Please enter a valid email address.';
    if (v.length > 254) return 'Email is too long.';
    return null;
  };

  const validateMessage = (value: string): string | null => {
    const v = value.replace(/\r\n/g, '\n'); // normalize newlines
    const trimmed = v.trim();
    if (!trimmed) return 'Feedback is required.';
    if (trimmed.length < MESSAGE_MIN) return `Please provide at least ${MESSAGE_MIN} characters.`;
    if (trimmed.length > MESSAGE_MAX) return `Feedback must be at most ${MESSAGE_MAX} characters.`;
    const lines = v.split('\n').length;
    if (lines > MESSAGE_MAX_LINES) return `Please keep it under ${MESSAGE_MAX_LINES} lines.`;
    return null;
  };

  // live validation on change
  const onEmailChange = (val: string) => {
    setEmail(val);
    setEmailError(validateEmail(val));
  };
  const onFeedbackChange = (val: string) => {
    setFeedback(val);
    setFeedbackError(validateMessage(val));
  };

  const charCount = feedback.length;
  const canSubmit = useMemo(() => {
    return !loading && !validateEmail(email) && !validateMessage(feedback);
  }, [loading, email, feedback]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // final validation before submit
    const eErr = validateEmail(email);
    const fErr = validateMessage(feedback);
    setEmailError(eErr);
    setFeedbackError(fErr);
    if (eErr || fErr) return;

    setLoading(true);
    try {
      const feedbackData: FeedbackData = {
        email: email.trim(),
        message: feedback.trim()
      };

      await submitFeedback(feedbackData);

      setSubmitted(true);
      setEmail('');
      setFeedback('');
      setEmailError(null);
      setFeedbackError(null);

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
    const hash = email.split('').reduce((a, b) => {
      a = ((a << 5) - a) + b.charCodeAt(0);
      return a & a;
    }, 0);
    const variants = ['primary', 'secondary', 'success', 'info', 'warning'];
    return variants[Math.abs(hash) % variants.length];
  };

  return (
    <Container className="pt-3 pb-4">
      <h1 className="h3 mb-3">Feedback / Bug Report</h1>

      {/* Feedback Form */}
      <Card className="mb-4 shadow-sm border-body">
        <Card.Header className="bg-body-tertiary">
          <h5 className="mb-0">Submit New Feedback</h5>
        </Card.Header>
        <Card.Body>
          {submitted && <Alert variant="success">Feedback submitted successfully!</Alert>}
          {error && <Alert variant="danger">{error}</Alert>}
          <Form onSubmit={handleSubmit} noValidate>
            <Form.Group controlId="feedbackEmail" className="mb-3">
              <Form.Label>Email address</Form.Label>
              <Form.Control
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => onEmailChange(e.target.value)}
                onBlur={(e) => setEmailError(validateEmail(e.target.value))}
                isInvalid={!!emailError}
                disabled={loading}
                autoComplete="email"
                inputMode="email"
                maxLength={254}
                required
              />
              <Form.Control.Feedback type="invalid">
                {emailError}
              </Form.Control.Feedback>
            </Form.Group>

            <Form.Group controlId="feedbackMessage" className="mb-2">
              <Form.Label>Feedback / Bug Description</Form.Label>
              <Form.Control
                as="textarea"
                rows={5}
                placeholder="Describe your feedback or bug here"
                value={feedback}
                onChange={(e) => onFeedbackChange(e.target.value)}
                onBlur={(e) => setFeedbackError(validateMessage(e.target.value))}
                isInvalid={!!feedbackError}
                disabled={loading}
                maxLength={MESSAGE_MAX}
                required
              />
              <div className="d-flex justify-content-between">
                <Form.Control.Feedback type="invalid">
                  {feedbackError}
                </Form.Control.Feedback>
                <small className="text-body-secondary ms-auto">
                  {charCount}/{MESSAGE_MAX}
                </small>
              </div>
              <Form.Text className="text-body-secondary">
                Tips: include steps to reproduce, expected vs. actual behavior, and any IDs/log snippets.
              </Form.Text>
            </Form.Group>

            <Button variant="primary" type="submit" disabled={!canSubmit}>
              {loading ? 'Submitting...' : 'Submit Feedback'}
            </Button>
          </Form>
        </Card.Body>
      </Card>

      {/* Feedback List */}
      <Card className="shadow-sm border-body">
        <Card.Header className="d-flex justify-content-between align-items-center bg-body-tertiary">
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
            <div className="text-center py-4 text-body-secondary">
              <h6>No feedback submitted yet</h6>
              <p className="text-body-secondary mb-0">Submitted feedback will appear here.</p>
            </div>
          ) : (
            <>
              <p className="text-body-secondary mb-3">
                Total submissions: <strong>{feedbacks.length}</strong>
              </p>
              <ThemedTable striped hover responsive className="mb-0">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Message</th>
                    <th>Created</th>
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
                        <small className="text-body-secondary">
                          {formatDate(feedbackItem.created_at)}
                        </small>
                      </td>
                      <td>
                        <div
                          style={{
                            maxWidth: '400px',
                            wordWrap: 'break-word',
                            whiteSpace: 'pre-wrap'
                          }}
                        >
                          {feedbackItem.message}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </ThemedTable>
            </>
          )}
        </Card.Body>
      </Card>
    </Container>
  );
};

export default FeedbackPage;
