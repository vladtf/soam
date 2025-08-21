import React from 'react';
import { Alert, Button, Card } from 'react-bootstrap';
import { FaExclamationTriangle, FaRedo } from 'react-icons/fa';

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: string;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error?: Error; resetError: () => void }>;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    // Update state so the next render will show the fallback UI
    return { 
      hasError: true, 
      error 
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log the error details for debugging
    console.error('ErrorBoundary caught an error:', error);
    console.error('Error details:', errorInfo);
    
    this.setState({
      hasError: true,
      error,
      errorInfo: errorInfo.componentStack || undefined
    });
  }

  resetError = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        const FallbackComponent = this.props.fallback;
        return <FallbackComponent error={this.state.error} resetError={this.resetError} />;
      }

      // Default fallback UI
      return (
        <Card className="border-danger">
          <Card.Header className="bg-danger text-white">
            <FaExclamationTriangle className="me-2" />
            Something went wrong
          </Card.Header>
          <Card.Body>
            <Alert variant="danger">
              <Alert.Heading>Error Details</Alert.Heading>
              <p><strong>Error:</strong> {this.state.error?.message}</p>
              {this.state.error?.stack && (
                <details>
                  <summary>Stack Trace</summary>
                  <pre className="text-small mt-2">{this.state.error.stack}</pre>
                </details>
              )}
              {this.state.errorInfo && (
                <details>
                  <summary>Component Stack</summary>
                  <pre className="text-small mt-2">{this.state.errorInfo}</pre>
                </details>
              )}
            </Alert>
            <Button variant="outline-primary" onClick={this.resetError}>
              <FaRedo className="me-2" />
              Try Again
            </Button>
          </Card.Body>
        </Card>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
