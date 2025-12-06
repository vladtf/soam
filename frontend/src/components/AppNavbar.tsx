import React, { useEffect, useMemo, useState } from 'react';
import { Navbar, Nav, Container, Button, Dropdown, Badge, NavDropdown } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { useError } from '../context/ErrorContext';
import { getConfig } from '../config';
import { isErrorReportingEnabled, setErrorReportingEnabled } from '../errors';
import UserSwitcher from './UserSwitcher';

const AppNavbar: React.FC = () => {
  const { theme, mode, toggleMode } = useTheme();
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
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
        // Using ingestor ready endpoint as health probe
        const { ingestorUrl } = getConfig();
        const response = await fetch(`${ingestorUrl}/api/ready`);
        if (!cancelled) setStatus(response.ok ? 'green' : 'red');
      } catch {
        if (!cancelled) setStatus('red');
      }
    };
    ping();
    const id = setInterval(ping, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const handleSignIn = () => {
    navigate('/login');
  };

  const handleSignOut = () => {
    logout();
    navigate('/');
  };
  
  const initials = useMemo(() => (user?.username ? user.username.trim().slice(0, 2).toUpperCase() : ''), [user]);
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
      style={{ 
        width: 'clamp(8px, 2vw, 12px)', 
        height: 'clamp(8px, 2vw, 12px)', 
        backgroundColor: status === 'green' ? '#28a745' : status === 'yellow' ? '#ffc107' : '#dc3545' 
      }}
      aria-label={`Status: ${status}`}
    />
  );

  return (
    <Navbar expand="lg" className="border-bottom border-body bg-body-tertiary">
      <Container>
        <Navbar.Brand href="/" className="d-flex align-items-center">
          <img 
            src="/soam.svg" 
            alt="SOAM" 
            style={{ height: '24px', width: '24px', marginRight: '8px' }}
          />
          SOAM
        </Navbar.Brand>
        <Navbar.Toggle aria-controls="basic-navbar-nav" />
        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="me-auto">
            <Nav.Link href="/dashboard">Dashboard</Nav.Link>
            <Nav.Link href="/monitoring">Monitoring</Nav.Link>
            <Nav.Link href="/pipeline">Data Pipeline</Nav.Link>
            <Nav.Link href="/data-sources">Data Sources</Nav.Link>
            <Nav.Link href="/minio">Data Browser</Nav.Link>
            <Nav.Link href="/metadata">Metadata</Nav.Link>
            <Nav.Link href="/troubleshooting">Troubleshooting</Nav.Link>
            <NavDropdown title="More" id="nav-more">
              <NavDropdown.Item href="/map">Map</NavDropdown.Item>
              <NavDropdown.Item href="/ontology">Ontology</NavDropdown.Item>
              <NavDropdown.Item href="/new-events">New Events</NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item href="/settings">Settings</NavDropdown.Item>
              <NavDropdown.Item href="/feedback">Feedback</NavDropdown.Item>
            </NavDropdown>
          </Nav>
          <Nav className="ms-auto align-items-center gap-2">
            <div className="d-flex align-items-center text-body-secondary small">
              {StatusDot}
              {envLabel && <Badge bg="light" text="dark" className="me-2">{envLabel}</Badge>}
            </div>
            <UserSwitcher />
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
              <Dropdown.Toggle size="sm" variant={isDark ? 'outline-light' : 'outline-dark'} className="d-flex align-items-center" aria-label={isAuthenticated ? `User menu for ${user?.username}` : 'User menu'}>
                {isAuthenticated && user ? (
                  <span className="d-inline-flex align-items-center justify-content-center rounded-circle bg-primary text-white" style={{ 
                    width: 'clamp(24px, 4vw, 32px)', 
                    height: 'clamp(24px, 4vw, 32px)', 
                    fontSize: 'clamp(10px, 2vw, 14px)' 
                  }}>
                    {initials}
                  </span>
                ) : 'Sign in'}
              </Dropdown.Toggle>
              <Dropdown.Menu>
                {!isAuthenticated && (
                  <Dropdown.Item onClick={handleSignIn}>Sign in</Dropdown.Item>
                )}
                {isAuthenticated && user && (
                  <>
                    <Dropdown.Header>
                      <div>Signed in as <strong>@{user.username}</strong></div>
                      <div className="mt-1">
                        {(user.roles || []).map((role) => (
                          <Badge 
                            key={role} 
                            bg={role === 'admin' ? 'danger' : role === 'user' ? 'primary' : 'secondary'} 
                            className="me-1"
                          >
                            {role.toUpperCase()}
                          </Badge>
                        ))}
                      </div>
                    </Dropdown.Header>
                    <Dropdown.Divider />
                    <Dropdown.Item
                      as="button"
                      className="d-flex align-items-center justify-content-between"
                      onClick={toggleErrorReporting}
                      aria-pressed={errorReporting}
                      aria-label={errorReporting ? 'Disable error reporting' : 'Enable error reporting'}
                      style={{ minWidth: 'max-content' }}
                    >
                      <span>Error reporting</span>
                      <span
                        className={`btn btn-sm ${errorReporting ? 'btn-success' : 'btn-outline-secondary'}`}
                        style={{ minWidth: '4.5rem', pointerEvents: 'none' }}
                      >
                        {errorReporting ? 'On' : 'Off'}
                      </span>
                    </Dropdown.Item>
                    <Dropdown.Divider />
                    <Dropdown.Item onClick={handleSignOut}>Sign out</Dropdown.Item>
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
