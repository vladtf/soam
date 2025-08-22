import React from 'react';
import { Alert, Button, Card } from 'react-bootstrap';
import { FaExclamationTriangle, FaRedo } from 'react-icons/fa';
import DevErrorOverlay, { DevErrorInfo } from './DevErrorOverlay';

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: React.ErrorInfo;
  devErrorInfo?: DevErrorInfo;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error?: Error; resetError: () => void }>;
  showDevOverlay?: boolean;
  context?: Record<string, unknown>;
  componentName?: string;
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
    
    // Create detailed dev error info
    const devErrorInfo: DevErrorInfo = {
      error,
      errorInfo,
      componentStack: errorInfo.componentStack || undefined,
      errorBoundary: this.props.componentName || 'ErrorBoundary',
      url: window.location.href,
      userAgent: navigator.userAgent,
      timestamp: new Date(),
      buildInfo: {
        mode: (import.meta as any).env?.MODE || 'development',
        commit: (import.meta as any).env?.VITE_GIT_COMMIT,
        version: (import.meta as any).env?.VITE_VERSION,
      },
      context: {
        ...this.props.context,
        props: this.props.children ? { type: typeof this.props.children } : undefined,
        location: {
          href: window.location.href,
          pathname: window.location.pathname,
          search: window.location.search,
          hash: window.location.hash,
        },
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight,
        },
        performance: {
          memory: (performance as any).memory ? {
            usedJSHeapSize: (performance as any).memory.usedJSHeapSize,
            totalJSHeapSize: (performance as any).memory.totalJSHeapSize,
            jsHeapSizeLimit: (performance as any).memory.jsHeapSizeLimit,
          } : undefined,
          timing: performance.timing ? {
            domLoading: performance.timing.domLoading,
            domComplete: performance.timing.domComplete,
            loadEventEnd: performance.timing.loadEventEnd,
          } : undefined,
        },
      },
    };

    this.setState({
      hasError: true,
      error,
      errorInfo,
      devErrorInfo,
    });

    // Report to error tracking system if enabled
    if (window.reportError) {
      try {
        window.reportError(error);
      } catch (reportingError) {
        console.warn('Failed to report error:', reportingError);
      }
    }
  }

  resetError = () => {
    this.setState({ 
      hasError: false, 
      error: undefined, 
      errorInfo: undefined,
      devErrorInfo: undefined 
    });
  };

  render() {
    if (this.state.hasError) {
      // Show development overlay if enabled and in development mode
      const isDevelopment = (import.meta as any).env?.MODE === 'development';
      const showDevOverlay = this.props.showDevOverlay !== false && isDevelopment;
      
      if (showDevOverlay && this.state.devErrorInfo) {
        return (
          <DevErrorOverlay
            errorInfo={this.state.devErrorInfo}
            onDismiss={this.resetError}
            onRetry={this.resetError}
          />
        );
      }

      // Custom fallback UI
      if (this.props.fallback) {
        const FallbackComponent = this.props.fallback;
        return <FallbackComponent error={this.state.error} resetError={this.resetError} />;
      }

      // Default fallback UI (production-friendly)
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
              
              {/* Show detailed error info only in development */}
              {isDevelopment && (
                <>
                  {this.state.error?.stack && (
                    <details className="mt-3">
                      <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>
                        Stack Trace
                      </summary>
                      <pre className="text-small mt-2 p-3 bg-light border rounded" style={{ 
                        fontSize: '0.75rem',
                        overflow: 'auto',
                        maxHeight: '300px'
                      }}>
                        {this.state.error.stack}
                      </pre>
                    </details>
                  )}
                  
                  {this.state.errorInfo?.componentStack && (
                    <details className="mt-3">
                      <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>
                        Component Stack
                      </summary>
                      <pre className="text-small mt-2 p-3 bg-light border rounded" style={{ 
                        fontSize: '0.75rem',
                        overflow: 'auto',
                        maxHeight: '200px'
                      }}>
                        {this.state.errorInfo.componentStack}
                      </pre>
                    </details>
                  )}

                  {this.props.context && (
                    <details className="mt-3">
                      <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>
                        Debug Context
                      </summary>
                      <pre className="text-small mt-2 p-3 bg-light border rounded" style={{ 
                        fontSize: '0.75rem',
                        overflow: 'auto',
                        maxHeight: '200px'
                      }}>
                        {JSON.stringify(this.props.context, null, 2)}
                      </pre>
                    </details>
                  )}
                </>
              )}
            </Alert>
            
            <div className="d-flex gap-2">
              <Button variant="outline-primary" onClick={this.resetError}>
                <FaRedo className="me-2" />
                Try Again
              </Button>
              
              {isDevelopment && (
                <Button 
                  variant="outline-secondary" 
                  onClick={() => {
                    const errorReport = {
                      error: {
                        name: this.state.error?.name,
                        message: this.state.error?.message,
                        stack: this.state.error?.stack,
                      },
                      errorInfo: this.state.errorInfo,
                      context: this.props.context,
                      timestamp: new Date().toISOString(),
                      url: window.location.href,
                    };
                    console.log('Error Report:', errorReport);
                    navigator.clipboard?.writeText(JSON.stringify(errorReport, null, 2));
                  }}
                >
                  Copy Error Report
                </Button>
              )}
            </div>
          </Card.Body>
        </Card>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
