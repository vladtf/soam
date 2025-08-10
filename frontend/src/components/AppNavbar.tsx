import React from 'react';
import { Navbar, Nav, Container, Button, Dropdown } from 'react-bootstrap';
import { FaCity, FaMoon, FaSun } from 'react-icons/fa';
import { Link } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';

const AppNavbar: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const { username, login, logout } = useAuth();
  const isDark = theme === 'dark';
  const promptLogin = () => {
    const name = window.prompt('Enter your username (letters, numbers, dot, dash, underscore):', username ?? '');
    if (name) login(name);
  };
  return (
    <Navbar bg={isDark ? 'dark' : 'light'} variant={isDark ? 'dark' : 'light'} expand="lg">
      <Container>
          <Navbar.Brand as={Link} to="/">
            <FaCity className="me-2" /> SOAM
          </Navbar.Brand>
        <Navbar.Toggle aria-controls="basic-navbar-nav" />
        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="me-auto">
              <Nav.Link as={Link} to="/sensor-data">Sensor Data</Nav.Link>
              <Nav.Link as={Link} to="/ontology">Ontology</Nav.Link>
              <Nav.Link as={Link} to="/dashboard">Dashboard</Nav.Link>
              <Nav.Link as={Link} to="/map">Map</Nav.Link>
              <Nav.Link as={Link} to="/new-events">New Events</Nav.Link>
              <Nav.Link as={Link} to="/minio">Data Browser</Nav.Link>
              <Nav.Link as={Link} to="/normalization">Normalization</Nav.Link>
              <Nav.Link as={Link} to="/feedback">Feedback</Nav.Link>
          </Nav>
          <Nav className="ms-auto align-items-center gap-2">
            <Button
              size="sm"
              variant={isDark ? 'outline-light' : 'outline-dark'}
              onClick={toggleTheme}
              aria-label="Toggle theme"
            >
              {isDark ? (<><FaSun className="me-1" /> Light</>) : (<><FaMoon className="me-1" /> Dark</>)}
            </Button>
            <Dropdown align="end">
              <Dropdown.Toggle size="sm" variant={isDark ? 'outline-light' : 'outline-dark'}>
                {username ? `@${username}` : 'Sign in'}
              </Dropdown.Toggle>
              <Dropdown.Menu>
                {!username && (
                  <Dropdown.Item onClick={promptLogin}>Sign in</Dropdown.Item>
                )}
                {username && (
                  <>
                    <Dropdown.Header>Signed in as @{username}</Dropdown.Header>
                    <Dropdown.Item onClick={promptLogin}>Change user…</Dropdown.Item>
                    <Dropdown.Divider />
                    <Dropdown.Item onClick={logout}>Sign out</Dropdown.Item>
                  </>
                )}
              </Dropdown.Menu>
            </Dropdown>
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
};

export default AppNavbar;
