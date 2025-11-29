import React, { useState, useEffect } from 'react';
import { Container, Card, Form, Button, Alert, Spinner, Tab, Tabs, Row, Col } from 'react-bootstrap';
import { useNavigate, useLocation } from 'react-router-dom';
import { FaSignInAlt, FaUserPlus, FaShieldAlt } from 'react-icons/fa';
import { useAuth } from '../context/AuthContext';

const LoginPage: React.FC = () => {
  const { login, register, isAuthenticated, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Form states
  const [activeTab, setActiveTab] = useState<string>('login');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Login form
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register form
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');

  // Get redirect path from location state
  const from = (location.state as { from?: string })?.from || '/';

  // Redirect if already authenticated
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, authLoading, navigate, from]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setIsSubmitting(true);

    try {
      await login(loginUsername, loginPassword);
      // Navigation will happen via useEffect
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    // Validation
    if (regPassword !== regConfirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (regPassword.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    setIsSubmitting(true);

    try {
      await register(regUsername, regEmail, regPassword);
      setSuccessMessage('Registration successful! You are now logged in.');
      // Navigation will happen via useEffect
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading) {
    return (
      <Container className="pt-3 pb-4">
        <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '50vh' }}>
          <Spinner animation="border" role="status">
            <span className="visually-hidden">Loading...</span>
          </Spinner>
        </div>
      </Container>
    );
  }

  return (
    <Container className="pt-3 pb-4">
      <h1 className="h3 mb-3"><FaShieldAlt className="me-2" />Authentication</h1>

      <Row className="justify-content-center">
        <Col md={8} lg={6} xl={5}>
          <Card className="shadow-sm border-body">
            <Card.Header className="bg-body-tertiary">
              <h5 className="mb-0">Sign In or Create Account</h5>
            </Card.Header>
            <Card.Body>
              {error && (
                <Alert variant="danger" dismissible onClose={() => setError(null)}>
                  {error}
                </Alert>
              )}
              {successMessage && (
                <Alert variant="success" dismissible onClose={() => setSuccessMessage(null)}>
                  {successMessage}
                </Alert>
              )}

              <Tabs
                activeKey={activeTab}
                onSelect={(k) => {
                  setActiveTab(k || 'login');
                  setError(null);
                  setSuccessMessage(null);
                }}
                className="mb-4"
                fill
              >
                <Tab eventKey="login" title={<><FaSignInAlt className="me-1" /> Login</>}>
                  <Form onSubmit={handleLogin}>
                    <Form.Group className="mb-3" controlId="loginUsername">
                      <Form.Label>Username</Form.Label>
                      <Form.Control
                        type="text"
                        placeholder="Enter your username"
                        value={loginUsername}
                        onChange={(e) => setLoginUsername(e.target.value)}
                        required
                        disabled={isSubmitting}
                        autoComplete="username"
                      />
                    </Form.Group>

                    <Form.Group className="mb-4" controlId="loginPassword">
                      <Form.Label>Password</Form.Label>
                      <Form.Control
                        type="password"
                        placeholder="Enter your password"
                        value={loginPassword}
                        onChange={(e) => setLoginPassword(e.target.value)}
                        required
                        disabled={isSubmitting}
                        autoComplete="current-password"
                      />
                    </Form.Group>

                    <div className="d-grid">
                      <Button variant="primary" type="submit" disabled={isSubmitting}>
                        {isSubmitting ? (
                          <>
                            <Spinner animation="border" size="sm" className="me-2" />
                            Signing in...
                          </>
                        ) : (
                          <>
                            <FaSignInAlt className="me-2" />
                            Sign In
                          </>
                        )}
                      </Button>
                    </div>
                  </Form>
                </Tab>

                <Tab eventKey="register" title={<><FaUserPlus className="me-1" /> Register</>}>
                  <Form onSubmit={handleRegister}>
                    <Form.Group className="mb-3" controlId="regUsername">
                      <Form.Label>Username</Form.Label>
                      <Form.Control
                        type="text"
                        placeholder="Choose a username"
                        value={regUsername}
                        onChange={(e) => setRegUsername(e.target.value)}
                        required
                        disabled={isSubmitting}
                        autoComplete="username"
                        minLength={3}
                      />
                      <Form.Text className="text-muted">
                        3-50 characters, letters, numbers, and underscores only
                      </Form.Text>
                    </Form.Group>

                    <Form.Group className="mb-3" controlId="regEmail">
                      <Form.Label>Email</Form.Label>
                      <Form.Control
                        type="email"
                        placeholder="Enter your email"
                        value={regEmail}
                        onChange={(e) => setRegEmail(e.target.value)}
                        required
                        disabled={isSubmitting}
                        autoComplete="email"
                      />
                    </Form.Group>

                    <Form.Group className="mb-3" controlId="regPassword">
                      <Form.Label>Password</Form.Label>
                      <Form.Control
                        type="password"
                        placeholder="Create a password"
                        value={regPassword}
                        onChange={(e) => setRegPassword(e.target.value)}
                        required
                        disabled={isSubmitting}
                        autoComplete="new-password"
                        minLength={8}
                      />
                      <Form.Text className="text-muted">
                        At least 8 characters
                      </Form.Text>
                    </Form.Group>

                    <Form.Group className="mb-4" controlId="regConfirmPassword">
                      <Form.Label>Confirm Password</Form.Label>
                      <Form.Control
                        type="password"
                        placeholder="Confirm your password"
                        value={regConfirmPassword}
                        onChange={(e) => setRegConfirmPassword(e.target.value)}
                        required
                        disabled={isSubmitting}
                        autoComplete="new-password"
                        minLength={8}
                      />
                    </Form.Group>

                    <div className="d-grid">
                      <Button variant="success" type="submit" disabled={isSubmitting}>
                        {isSubmitting ? (
                          <>
                            <Spinner animation="border" size="sm" className="me-2" />
                            Creating account...
                          </>
                        ) : (
                          <>
                            <FaUserPlus className="me-2" />
                            Create Account
                          </>
                        )}
                      </Button>
                    </div>
                  </Form>
                </Tab>
              </Tabs>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default LoginPage;
