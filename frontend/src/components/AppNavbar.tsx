import React, { useEffect, useMemo, useState } from 'react';
import { Navbar, Nav, Container, Button, Dropdown, Badge, NavDropdown } from 'react-bootstrap';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { useError } from '../context/ErrorContext';
import { getConfig } from '../config';
import { fetchConnections } from '../api/backendRequests';
import { isErrorReportingEnabled, setErrorReportingEnabled } from '../errors';

const AppNavbar: React.FC = () => {
  const { theme, mode, toggleMode } = useTheme();
  const { username, login, logout } = useAuth();
  const isDark = theme === 'dark';

  // backend connectivity status
  const [status, setStatus] = useState<'green' | 'yellow' | 'red'>('red');
  const [envLabel, setEnvLabel] = useState<string>('');

  useEffect(() => {
    // derive env from config URL
    try {
      const { backendUrl } = getConfig();
      if (backendUrl.includes('localhost') || backendUrl.includes('127.0.0.1')) setEnvLabel('Local');
      else if (/\.azure\.|\baksc\b|\.cloudapp\./i.test(backendUrl)) setEnvLabel('K8s');
      else setEnvLabel('Dev');
    } catch {
      setEnvLabel('');
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      try {
        // Using connections API as a lightweight health probe
        await fetchConnections();
        if (!cancelled) setStatus('green');
      } catch {
        if (!cancelled) setStatus('red');
      }
    };
    ping();
    const id = setInterval(ping, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);
  const promptLogin = () => {
    const name = window.prompt('Enter your username (letters, numbers, dot, dash, underscore):', username ?? '');
    if (name) login(name);
  };
  
  const initials = useMemo(() => (username ? username.trim().slice(0, 2).toUpperCase() : ''), [username]);
  const { openCenter } = useError();
  const [errorReporting, setErrorReporting] = useState<boolean>(false);

  // Initialize error reporting flag from storage
  useEffect(() => {
    setErrorReporting(isErrorReportingEnabled());
    const handler = (e: CustomEvent<{ enabled: boolean }>) => {
      if (e.detail && typeof e.detail.enabled === 'boolean') {
        setErrorReporting(e.detail.enabled);
      } else {
        setErrorReporting(isErrorReportingEnabled());
      }
    };
    window.addEventListener('soam:error-reporting-changed', handler as EventListener);
    return () => window.removeEventListener('soam:error-reporting-changed', handler as EventListener);
  }, []);

  const toggleErrorReporting = () => {
    const next = !errorReporting;
    setErrorReporting(next);
    setErrorReportingEnabled(next);
  };

  const StatusDot = (
    <span
      className="d-inline-block rounded-circle me-2"
      style={{ width: 10, height: 10, backgroundColor: status === 'green' ? '#28a745' : status === 'yellow' ? '#ffc107' : '#dc3545' }}
      aria-label={`Status: ${status}`}
    />
  );

  return (
    <Navbar expand="lg" className="border-bottom border-body bg-body-tertiary">
      <Container>
        <Navbar.Brand href="/">SOAM</Navbar.Brand>
        <Navbar.Toggle aria-controls="basic-navbar-nav" />
        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="me-auto">
            <Nav.Link href="/dashboard">Dashboard</Nav.Link>
            <Nav.Link href="/sensor-data">Sensor Data</Nav.Link>
            <Nav.Link href="/computations">Computations</Nav.Link>
            <Nav.Link href="/normalization">Normalization</Nav.Link>
            <NavDropdown title="More" id="nav-more">
              <NavDropdown.Item href="/map">Map</NavDropdown.Item>
              <NavDropdown.Item href="/minio">Data Browser</NavDropdown.Item>
              <NavDropdown.Item href="/ontology">Ontology</NavDropdown.Item>
              <NavDropdown.Item href="/new-events">New Events</NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="/feedback">Feedback</NavDropdown.Item>
              <NavDropdown.Item href="/troubleshooting">Troubleshooting</NavDropdown.Item>
            </NavDropdown>
          </Nav>
          <Nav className="ms-auto align-items-center gap-2">
            <div className="d-flex align-items-center text-body-secondary small">
              {StatusDot}
              {envLabel && <Badge bg="light" text="dark" className="me-2">{envLabel}</Badge>}
            </div>
            <Button size="sm" variant={isDark ? 'outline-light' : 'outline-dark'} onClick={openCenter} aria-label="Open Errors" title="Errors">!</Button>
            <Button
              size="sm"
              variant={isDark ? 'outline-light' : 'outline-dark'}
              onClick={toggleMode}
              aria-label={mode === 'auto' ? 'Theme: Auto (system)' : `Theme: ${mode}`}
              title={mode === 'auto' ? 'Theme: Auto (system)' : `Theme: ${mode}`}
            >
              {mode === 'auto' ? 'A' : isDark ? 'Light' : 'Dark'}
            </Button>
            <Dropdown align="end">
              <Dropdown.Toggle size="sm" variant={isDark ? 'outline-light' : 'outline-dark'} className="d-flex align-items-center" aria-label={username ? `User menu for ${username}` : 'User menu'}>
                {username ? (
                  <span className="d-inline-flex align-items-center justify-content-center rounded-circle bg-primary text-white" style={{ width: 28, height: 28, fontSize: 12 }}>
                    {initials}
                  </span>
                ) : 'Sign in'}
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
                    <Dropdown.Item
                      as="button"
                      className="d-flex align-items-center justify-content-between"
                      onClick={toggleErrorReporting}
                      aria-pressed={errorReporting}
                      aria-label={errorReporting ? 'Disable error reporting' : 'Enable error reporting'}
                      style={{ minWidth: 70 }}
                    >
                      <span>Error reporting</span>
                      <span
                        className={`btn btn-sm ${errorReporting ? 'btn-success' : 'btn-outline-secondary'}`}
                        style={{ minWidth: 70, pointerEvents: 'none' }}
                      >
                        {errorReporting ? 'On' : 'Off'}
                      </span>
                    </Dropdown.Item>
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
