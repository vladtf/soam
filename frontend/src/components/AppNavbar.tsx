import React from 'react';
import { Navbar, Nav, Container } from 'react-bootstrap';
import { LinkContainer } from 'react-router-bootstrap';

const AppNavbar: React.FC = () => {
  return (
    <Navbar bg="dark" variant="dark" expand="lg">
      <Container>
        <Navbar.Brand>My App</Navbar.Brand>
        <Navbar.Toggle aria-controls="basic-navbar-nav" />
        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="me-auto">
            {/* <LinkContainer to="/"> */}
              <Nav.Link href="/">Home</Nav.Link>
            {/* </LinkContainer> */}
            {/* <LinkContainer to="/sensor-data"> */}
              <Nav.Link href="/sensor-data">Sensor Data</Nav.Link>
            {/* </LinkContainer> */}
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
};

export default AppNavbar;
