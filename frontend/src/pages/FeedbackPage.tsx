import React, { useState } from 'react';
import { Container, Form, Button, Alert } from 'react-bootstrap';

const FeedbackPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [feedback, setFeedback] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Replace with your submission logic, e.g., API call
    console.log({ email, feedback });
    setSubmitted(true);
    setEmail('');
    setFeedback('');
  };

  return (
    <Container className="mt-4">
      <h1>Submit Feedback / Bug Report</h1>
      {submitted && <Alert variant="success">Feedback submitted successfully!</Alert>}
      <Form onSubmit={handleSubmit}>
        <Form.Group controlId="feedbackEmail" className="mb-3">
          <Form.Label>Email address</Form.Label>
          <Form.Control 
            type="email" 
            placeholder="Enter your email" 
            value={email} 
            onChange={(e) => setEmail(e.target.value)} 
            required 
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
          />
        </Form.Group>
        <Button variant="primary" type="submit">
          Submit Feedback
        </Button>
      </Form>
    </Container>
  );
};

export default FeedbackPage;
