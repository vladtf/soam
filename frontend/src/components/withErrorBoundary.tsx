import React from 'react';
import ErrorBoundary from './ErrorBoundary';

interface WithErrorBoundaryOptions {
  fallback?: React.ComponentType<{ error?: Error; resetError: () => void }>;
  showDevOverlay?: boolean;
  context?: Record<string, unknown>;
  componentName?: string;
}

export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  options: WithErrorBoundaryOptions = {}
) {
  const WrappedComponent = (props: P) => {
    const context = {
      ...options.context,
      componentName: Component.displayName || Component.name,
      props: (import.meta as any).env?.MODE === 'development' ? props : undefined,
    };

    return (
      <ErrorBoundary
        fallback={options.fallback}
        showDevOverlay={options.showDevOverlay}
        context={context}
        componentName={options.componentName || Component.displayName || Component.name}
      >
        <Component {...props} />
      </ErrorBoundary>
    );
  };

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;

  return WrappedComponent;
}

// Utility function to create an error boundary with specific configuration
export function createErrorBoundary(options: WithErrorBoundaryOptions = {}) {
  return function ErrorBoundaryWrapper({ children }: { children: React.ReactNode }) {
    return (
      <ErrorBoundary
        fallback={options.fallback}
        showDevOverlay={options.showDevOverlay}
        context={options.context}
        componentName={options.componentName}
      >
        {children}
      </ErrorBoundary>
    );
  };
}

// Pre-configured error boundaries for common use cases
export const PageErrorBoundary = createErrorBoundary({
  componentName: 'PageErrorBoundary',
  showDevOverlay: true,
});

export const ComponentErrorBoundary = createErrorBoundary({
  componentName: 'ComponentErrorBoundary',
  showDevOverlay: true,
});

export const APIErrorBoundary = createErrorBoundary({
  componentName: 'APIErrorBoundary',
  context: { type: 'api_interaction' },
  showDevOverlay: true,
});

export default withErrorBoundary;
