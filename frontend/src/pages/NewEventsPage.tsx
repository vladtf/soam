import React, { useState } from 'react';
import { Container, Form, Button } from 'react-bootstrap';

const NewEventsPage: React.FC = () => {
  const [eventTitle, setEventTitle] = useState("");
  const [eventDescription, setEventDescription] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // For now, simply print the event to console
    console.log("New event:", { eventTitle, eventDescription });
    // Reset form fields
    setEventTitle("");
    setEventDescription("");
  };

  return (
    <Container className="mt-3">
      <h1>Create New Event</h1>
      <Form onSubmit={handleSubmit}>
        <Form.Group controlId="eventTitle" className="mb-3">
          <Form.Label>Event Title</Form.Label>
          <Form.Control
            type="text"
            placeholder="Enter event title"
            value={eventTitle}
            onChange={(e) => setEventTitle(e.target.value)}
            required
          />
        </Form.Group>
        <Form.Group controlId="eventDescription" className="mb-3">
          <Form.Label>Event Description</Form.Label>
          <Form.Control
            as="textarea"
            rows={3}
            placeholder="Enter event description"
            value={eventDescription}
            onChange={(e) => setEventDescription(e.target.value)}
            required
          />
        </Form.Group>
        <Button variant="primary" type="submit">
          Add Event
        </Button>
      </Form>
    </Container>
  );
};

export default NewEventsPage;
