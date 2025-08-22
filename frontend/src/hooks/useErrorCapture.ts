import { useCallback, useRef } from 'react';
import { useError } from '../context/ErrorContext';

export interface ErrorContext {
  component?: string;
  action?: string;
  props?: Record<string, unknown>;
  state?: Record<string, unknown>;
  user?: {
    id?: string;
    role?: string;
  };
  [key: string]: unknown;
}

export interface CapturedError {
  message: string;
  stack?: string;
  cause?: Error;
  context?: ErrorContext;
  timestamp: Date;
  url: string;
  userAgent: string;
}

export function useErrorCapture() {
  const { setError } = useError();
  const contextRef = useRef<ErrorContext>({});

  const setContext = useCallback((context: Partial<ErrorContext>) => {
    contextRef.current = { ...contextRef.current, ...context };
  }, []);

  const clearContext = useCallback(() => {
    contextRef.current = {};
  }, []);

  const captureError = useCallback((error: Error | string, additionalContext?: Partial<ErrorContext>) => {
    const errorObj = typeof error === 'string' ? new Error(error) : error;
    
    const capturedError: CapturedError = {
      message: errorObj.message,
      stack: errorObj.stack,
      cause: (errorObj as any).cause as Error | undefined,
      context: {
        ...contextRef.current,
        ...additionalContext,
      },
      timestamp: new Date(),
      url: window.location.href,
      userAgent: navigator.userAgent,
    };

    // Log detailed error for development
    if ((import.meta as any).env?.MODE === 'development') {
      console.group('🚨 Error Captured');
      console.error('Error:', errorObj);
      console.log('Context:', capturedError.context);
      console.log('Full Error Details:', capturedError);
      console.groupEnd();
    }

    // Report to error tracking
    setError(errorObj);

    return capturedError;
  }, [setError]);

  const wrapAsync = useCallback(<T extends (...args: any[]) => Promise<any>>(
    asyncFn: T,
    context?: Partial<ErrorContext>
  ): T => {
    return (async (...args: Parameters<T>) => {
      try {
        return await asyncFn(...args);
      } catch (error) {
        captureError(error as Error, {
          ...context,
          action: context?.action || asyncFn.name || 'async_operation',
          args: args.length > 0 ? args : undefined,
        });
        throw error; // Re-throw to maintain original behavior
      }
    }) as T;
  }, [captureError]);

  const wrapSync = useCallback(<T extends (...args: any[]) => any>(
    syncFn: T,
    context?: Partial<ErrorContext>
  ): T => {
    return ((...args: Parameters<T>) => {
      try {
        return syncFn(...args);
      } catch (error) {
        captureError(error as Error, {
          ...context,
          action: context?.action || syncFn.name || 'sync_operation',
          args: args.length > 0 ? args : undefined,
        });
        throw error; // Re-throw to maintain original behavior
      }
    }) as T;
  }, [captureError]);

  const safeAsync = useCallback(<T extends (...args: any[]) => Promise<any>>(
    asyncFn: T,
    fallback?: any,
    context?: Partial<ErrorContext>
  ) => {
    return async (...args: Parameters<T>) => {
      try {
        return await asyncFn(...args);
      } catch (error) {
        captureError(error as Error, {
          ...context,
          action: context?.action || asyncFn.name || 'safe_async_operation',
          args: args.length > 0 ? args : undefined,
        });
        return fallback;
      }
    };
  }, [captureError]);

  const safeSync = useCallback(<T extends (...args: any[]) => any>(
    syncFn: T,
    fallback?: any,
    context?: Partial<ErrorContext>
  ) => {
    return (...args: Parameters<T>) => {
      try {
        return syncFn(...args);
      } catch (error) {
        captureError(error as Error, {
          ...context,
          action: context?.action || syncFn.name || 'safe_sync_operation',
          args: args.length > 0 ? args : undefined,
        });
        return fallback;
      }
    };
  }, [captureError]);

  return {
    captureError,
    setContext,
    clearContext,
    wrapAsync,
    wrapSync,
    safeAsync,
    safeSync,
  };
}

// Global error handler for unhandled promise rejections and errors
export function setupGlobalErrorHandlers() {
  // Unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    
    // Create a more detailed error for promise rejections
    const error = event.reason instanceof Error 
      ? event.reason 
      : new Error(String(event.reason));
    
    // Add additional context
    (error as any).type = 'unhandledrejection';
    (error as any).url = window.location.href;
    (error as any).timestamp = new Date().toISOString();
    
    // Prevent default browser behavior
    event.preventDefault();
    
    // Report the error
    if (window.dispatchEvent) {
      window.dispatchEvent(new CustomEvent('soam:error', { detail: error }));
    }
  });

  // Global error handler for JavaScript errors
  window.addEventListener('error', (event) => {
    const error = event.error || new Error(event.message);
    
    // Add additional context
    (error as any).filename = event.filename;
    (error as any).lineno = event.lineno;
    (error as any).colno = event.colno;
    (error as any).type = 'javascript_error';
    (error as any).url = window.location.href;
    (error as any).timestamp = new Date().toISOString();
    
    console.error('Global JavaScript error:', error);
    
    // Report the error
    if (window.dispatchEvent) {
      window.dispatchEvent(new CustomEvent('soam:error', { detail: error }));
    }
  });

  // Resource loading errors (images, scripts, etc.)
  window.addEventListener('error', (event) => {
    if (event.target !== window) {
      const target = event.target as HTMLElement;
      const error = new Error(`Resource failed to load: ${target.tagName}`);
      
      (error as any).type = 'resource_error';
      (error as any).element = target.tagName;
      (error as any).src = (target as any).src || (target as any).href;
      (error as any).url = window.location.href;
      (error as any).timestamp = new Date().toISOString();
      
      console.warn('Resource loading error:', error);
      
      // Report the error (but don't prevent default for resource errors)
      if (window.dispatchEvent) {
        window.dispatchEvent(new CustomEvent('soam:error', { detail: error }));
      }
    }
  }, true);
}

// Initialize global error handling when this module is imported
if (typeof window !== 'undefined') {
  setupGlobalErrorHandlers();
}
