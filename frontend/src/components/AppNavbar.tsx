import React from 'react';
import { Navbar, Nav, Container } from 'react-bootstrap';
import { FaCity } from 'react-icons/fa';
import { Link } from 'react-router-dom';

const AppNavbar: React.FC = () => {
  return (
    <Navbar bg="dark" variant="dark" expand="lg">
      <Container>
          <Navbar.Brand as={Link} to="/">
            <FaCity className="me-2" /> SOAM
          </Navbar.Brand>
        <Navbar.Toggle aria-controls="basic-navbar-nav" />
        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="me-auto">
              <Nav.Link as={Link} to="/sensor-data">Sensor Data</Nav.Link>
              <Nav.Link as={Link} to="/ontology">Ontology</Nav.Link>
              <Nav.Link as={Link} to="/dashboard">Dashboard</Nav.Link> {/* new link */}
              <Nav.Link as={Link} to="/map">Map</Nav.Link>
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
};

export default AppNavbar;
