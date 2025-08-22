// Development utilities for better error handling and debugging

import React from 'react';
import { useErrorCapture } from '../hooks/useErrorCapture';

declare global {
  interface Window {
    __SOAM_DEV_TOOLS__?: {
      captureError: (error: Error | string, context?: any) => void;
      enableErrorReporting: () => void;
      disableErrorReporting: () => void;
      showDebugPanel: () => void;
    };
  }
}

// Make error capture available globally for debugging
export function initializeDevTools() {
  if ((import.meta as any).env?.MODE !== 'development' || typeof window === 'undefined') {
    return;
  }

  const errorCapture = {
    captureError: (error: Error | string, context?: any) => {
      console.error('Manual error capture:', error, context);
      const errorObj = typeof error === 'string' ? new Error(error) : error;
      
      // Dispatch a custom event that error boundaries can listen to
      window.dispatchEvent(new CustomEvent('soam:error', { 
        detail: { error: errorObj, context } 
      }));
    },
    
    enableErrorReporting: () => {
      try {
        localStorage.setItem('soam_error_reporting_enabled', '1');
        console.log('✅ Error reporting enabled');
      } catch (e) {
        console.warn('Failed to enable error reporting:', e);
      }
    },
    
    disableErrorReporting: () => {
      try {
        localStorage.setItem('soam_error_reporting_enabled', '0');
        console.log('❌ Error reporting disabled');
      } catch (e) {
        console.warn('Failed to disable error reporting:', e);
      }
    },
    
    showDebugPanel: () => {
      // Dispatch event to show debug panel
      window.dispatchEvent(new CustomEvent('soam:show-debug-panel'));
      console.log('🐛 Debug panel requested');
    }
  };

  window.__SOAM_DEV_TOOLS__ = errorCapture;

  // Add keyboard shortcut to open debug panel (Ctrl+Shift+D)
  const handleKeydown = (event: KeyboardEvent) => {
    if (event.ctrlKey && event.shiftKey && event.key === 'D') {
      event.preventDefault();
      errorCapture.showDebugPanel();
    }
  };

  document.addEventListener('keydown', handleKeydown);

  // Log welcome message
  console.group('🚀 SOAM Development Tools');
  console.log('Debug tools are available in the global __SOAM_DEV_TOOLS__ object:');
  console.log('• __SOAM_DEV_TOOLS__.captureError(error, context) - Manually capture errors');
  console.log('• __SOAM_DEV_TOOLS__.enableErrorReporting() - Enable error reporting');
  console.log('• __SOAM_DEV_TOOLS__.disableErrorReporting() - Disable error reporting');
  console.log('• __SOAM_DEV_TOOLS__.showDebugPanel() - Show debug panel');
  console.log('• Press Ctrl+Shift+D to open the debug panel');
  console.groupEnd();

  // Return cleanup function
  return () => {
    document.removeEventListener('keydown', handleKeydown);
    if (window.__SOAM_DEV_TOOLS__) {
      delete window.__SOAM_DEV_TOOLS__;
    }
  };
}

// Utility function to wrap any function with error capture
export function withErrorCapture<T extends (...args: any[]) => any>(
  fn: T,
  context?: string
): T {
  if ((import.meta as any).env?.MODE !== 'development') {
    return fn; // In production, just return the original function
  }

  return ((...args: Parameters<T>) => {
    try {
      return fn(...args);
    } catch (error) {
      console.error(`Error in ${context || fn.name || 'anonymous function'}:`, error);
      
      // Enhance error with context
      const enhancedError = error instanceof Error ? error : new Error(String(error));
      (enhancedError as any).context = context;
      (enhancedError as any).functionName = fn.name;
      (enhancedError as any).arguments = args;
      
      // Dispatch error event
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('soam:error', { 
          detail: { error: enhancedError, context: { function: context || fn.name, args } }
        }));
      }
      
      throw enhancedError;
    }
  }) as T;
}

// Utility to add detailed logging to async functions
export function withAsyncErrorCapture<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  context?: string
): T {
  if ((import.meta as any).env?.MODE !== 'development') {
    return fn;
  }

  return (async (...args: Parameters<T>) => {
    const startTime = Date.now();
    const functionName = context || fn.name || 'async function';
    
    try {
      console.log(`⏳ Starting ${functionName}`, args);
      const result = await fn(...args);
      const duration = Date.now() - startTime;
      console.log(`✅ Completed ${functionName} (${duration}ms)`, result);
      return result;
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`❌ Failed ${functionName} (${duration}ms):`, error);
      
      const enhancedError = error instanceof Error ? error : new Error(String(error));
      (enhancedError as any).context = context;
      (enhancedError as any).functionName = fn.name;
      (enhancedError as any).arguments = args;
      (enhancedError as any).duration = duration;
      
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('soam:error', { 
          detail: { 
            error: enhancedError, 
            context: { 
              function: functionName, 
              args, 
              duration,
              type: 'async_operation'
            }
          }
        }));
      }
      
      throw enhancedError;
    }
  }) as T;
}

// React hook for components to easily report their errors
export function useComponentErrorHandler(componentName: string) {
  const { captureError, setContext } = useErrorCapture();

  React.useEffect(() => {
    setContext({ component: componentName });
    
    return () => {
      setContext({});
    };
  }, [componentName, setContext]);

  const handleError = React.useCallback((error: Error | string, action?: string) => {
    return captureError(error, { component: componentName, action });
  }, [captureError, componentName]);

  const wrapAction = React.useCallback((action: string, fn: () => void | Promise<void>) => {
    return async () => {
      try {
        await fn();
      } catch (error) {
        handleError(error as Error, action);
        throw error;
      }
    };
  }, [handleError]);

  return {
    handleError,
    wrapAction,
  };
}

// Initialize dev tools when this module is loaded
if ((import.meta as any).env?.MODE === 'development') {
  initializeDevTools();
}

export default {
  initializeDevTools,
  withErrorCapture,
  withAsyncErrorCapture,
  useComponentErrorHandler,
};
