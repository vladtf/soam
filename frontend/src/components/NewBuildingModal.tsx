import React, { useState, useEffect } from 'react';
import { Modal, Button, Form } from 'react-bootstrap';

interface NewBuildingModalProps {
  show: boolean;
  lat: number;
  lng: number;
  selectedBuilding: string;
  selectedAddress: string;
  selectedCity: string;
  selectedCountry: string;
  handleClose: () => void;
  onSubmit: (building: { name: string; description: string; street: string; city: string; country: string; lat: number; lng: number; }) => void;
}

const NewBuildingModal: React.FC<NewBuildingModalProps> = ({ show, lat, lng, selectedBuilding, selectedAddress, selectedCity, selectedCountry,
  handleClose, onSubmit }) => {
  const [name, setName] = useState(selectedBuilding);
  const [description, setDescription] = useState('Description of the building');
  const [street, setStreet] = useState(selectedAddress);
  const [city, setCity] = useState(selectedCity);
  const [country, setCountry] = useState(selectedCountry);

  // Update state when props change
  useEffect(() => {
    setName(selectedBuilding);
    setStreet(selectedAddress);
    setCity(selectedCity);
    setCountry(selectedCountry);
  }, [selectedAddress, selectedCity, selectedCountry]);

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ name, description, street, city, country, lat, lng });
    setName('');
    setDescription('Description of the building');
    setStreet('Street Name');
    setCity('Bucharest');
    setCountry('Romania');
  };

  return (
    <Modal show={show} onHide={handleClose}>
      <Modal.Header closeButton>
        <Modal.Title>Add New Building</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Form onSubmit={handleFormSubmit}>
          <Form.Group controlId="buildingName" className="mb-3">
            <Form.Label>Building Name</Form.Label>
            <Form.Control
              type="text"
              placeholder="Enter building name"
              value={name}
              onChange={e => setName(e.target.value)}
              required
            />
          </Form.Group>
          <Form.Group controlId="description" className="mb-3">
            <Form.Label>Description</Form.Label>
            <Form.Control
              type="text"
              placeholder="Enter building description"
              value={description}
              onChange={e => setDescription(e.target.value)}
              required
            />
          </Form.Group>
          <Form.Group controlId="street" className="mb-3">
            <Form.Label>Street</Form.Label>
            <Form.Control
              type="text"
              placeholder="Enter street"
              value={street}
              onChange={e => setStreet(e.target.value)}
              required
            />
          </Form.Group>
          <Form.Group controlId="city" className="mb-3">
            <Form.Label>City</Form.Label>
            <Form.Control
              type="text"
              placeholder="Enter city"
              value={city}
              onChange={e => setCity(e.target.value)}
              required
            />
          </Form.Group>
          <Form.Group controlId="country" className="mb-3">
            <Form.Label>Country</Form.Label>
            <Form.Control
              type="text"
              placeholder="Enter country"
              value={country}
              onChange={e => setCountry(e.target.value)}
              required
            />
          </Form.Group>
          <Form.Group controlId="latitude" className="mb-3">
            <Form.Label>Latitude</Form.Label>
            <Form.Control type="text" value={lat} readOnly />
          </Form.Group>
          <Form.Group controlId="longitude" className="mb-3">
            <Form.Label>Longitude</Form.Label>
            <Form.Control type="text" value={lng} readOnly />
          </Form.Group>
          <Button variant="primary" type="submit">
            Add Building
          </Button>
        </Form>
      </Modal.Body>
    </Modal>
  );
};

export default NewBuildingModal;
