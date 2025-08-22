import React from 'react';
import { toast } from 'react-toastify';

export interface NetworkError extends Error {
  status?: number;
  statusText?: string;
  url?: string;
  method?: string;
  response?: any;
  requestBody?: any;
  headers?: Record<string, string>;
}

export interface NetworkErrorDetails {
  error: NetworkError;
  request: {
    url: string;
    method: string;
    headers?: Record<string, string>;
    body?: any;
  };
  response?: {
    status: number;
    statusText: string;
    headers?: Record<string, string>;
    body?: any;
  };
  timestamp: Date;
  duration?: number;
}

class NetworkErrorHandler {
  private static instance: NetworkErrorHandler;
  private listeners: ((errorDetails: NetworkErrorDetails) => void)[] = [];

  static getInstance(): NetworkErrorHandler {
    if (!NetworkErrorHandler.instance) {
      NetworkErrorHandler.instance = new NetworkErrorHandler();
    }
    return NetworkErrorHandler.instance;
  }

  addListener(callback: (errorDetails: NetworkErrorDetails) => void) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(l => l !== callback);
    };
  }

  private notifyListeners(errorDetails: NetworkErrorDetails) {
    this.listeners.forEach(listener => {
      try {
        listener(errorDetails);
      } catch (err) {
        console.error('Error in network error listener:', err);
      }
    });
  }

  createError(response: Response, requestDetails: { url: string; method: string; body?: any; headers?: Record<string, string> }): NetworkError {
    const error = new Error(`HTTP ${response.status}: ${response.statusText}`) as NetworkError;
    error.name = 'NetworkError';
    error.status = response.status;
    error.statusText = response.statusText;
    error.url = requestDetails.url;
    error.method = requestDetails.method;
    return error;
  }

  async handleError(
    error: NetworkError,
    requestDetails: { url: string; method: string; body?: any; headers?: Record<string, string> },
    response?: Response,
    startTime?: number
  ): Promise<NetworkErrorDetails> {
    const timestamp = new Date();
    const duration = startTime ? timestamp.getTime() - startTime : undefined;

    // Try to extract response body for debugging
    let responseBody;
    if (response) {
      try {
        const clonedResponse = response.clone();
        const contentType = response.headers.get('content-type');
        if (contentType?.includes('application/json')) {
          responseBody = await clonedResponse.json();
        } else {
          responseBody = await clonedResponse.text();
        }
      } catch {
        responseBody = 'Could not parse response body';
      }
    }

    const errorDetails: NetworkErrorDetails = {
      error,
      request: requestDetails,
      response: response ? {
        status: response.status,
        statusText: response.statusText,
        headers: Object.fromEntries(response.headers.entries()),
        body: responseBody,
      } : undefined,
      timestamp,
      duration,
    };

    // Log detailed error in development
    if ((import.meta as any).env?.MODE === 'development') {
      console.group(`🌐 Network Error: ${error.method} ${error.url}`);
      console.error('Error:', error);
      console.log('Request:', errorDetails.request);
      if (errorDetails.response) {
        console.log('Response:', errorDetails.response);
      }
      if (duration) {
        console.log(`Duration: ${duration}ms`);
      }
      console.groupEnd();
    }

    // Show user-friendly error message
    this.showUserError(errorDetails);

    // Notify listeners
    this.notifyListeners(errorDetails);

    return errorDetails;
  }

  private showUserError(errorDetails: NetworkErrorDetails) {
    const { error, response } = errorDetails;
    
    let message = 'Network request failed';
    let type: 'error' | 'warning' = 'error';

    if (error.status) {
      switch (true) {
        case error.status >= 500:
          message = `Server error (${error.status}). Please try again later.`;
          break;
        case error.status === 404:
          message = 'The requested resource was not found.';
          break;
        case error.status === 403:
          message = 'You don\'t have permission to access this resource.';
          break;
        case error.status === 401:
          message = 'Your session has expired. Please log in again.';
          break;
        case error.status >= 400:
          message = response?.body?.message || response?.body?.detail || `Client error (${error.status})`;
          type = 'warning';
          break;
        default:
          message = `Request failed (${error.status})`;
      }
    } else if (error.message.toLowerCase().includes('network')) {
      message = 'Network connection error. Please check your internet connection.';
    }

    // Show toast notification
    if (type === 'error') {
      toast.error(message, {
        toastId: `network-error-${error.status}-${error.url}`, // Prevent duplicates
        autoClose: 7000,
      });
    } else {
      toast.warning(message, {
        toastId: `network-warning-${error.status}-${error.url}`,
        autoClose: 5000,
      });
    }
  }
}

// Enhanced fetch wrapper with error handling
export async function fetchWithErrorHandling(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const startTime = Date.now();
  const errorHandler = NetworkErrorHandler.getInstance();
  
  const requestDetails = {
    url,
    method: options.method || 'GET',
    body: options.body,
    headers: options.headers as Record<string, string> || {},
  };

  try {
    const response = await fetch(url, options);
    
    if (!response.ok) {
      const error = errorHandler.createError(response, requestDetails);
      await errorHandler.handleError(error, requestDetails, response, startTime);
      throw error;
    }

    // Log successful requests in development
    if ((import.meta as any).env?.MODE === 'development') {
      const duration = Date.now() - startTime;
      console.log(`✅ ${requestDetails.method} ${url} - ${response.status} (${duration}ms)`);
    }

    return response;
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      // Network error (no internet, CORS, etc.)
      const networkError = new Error('Network request failed') as NetworkError;
      networkError.name = 'NetworkError';
      networkError.url = url;
      networkError.method = requestDetails.method;
      
      await errorHandler.handleError(networkError, requestDetails, undefined, startTime);
      throw networkError;
    }
    
    // Re-throw if it's already been handled or is a different type of error
    throw error;
  }
}

// Hook to listen to network errors
export function useNetworkErrorHandler() {
  const [errors, setErrors] = React.useState<NetworkErrorDetails[]>([]);

  React.useEffect(() => {
    const errorHandler = NetworkErrorHandler.getInstance();
    
    const unsubscribe = errorHandler.addListener((errorDetails) => {
      setErrors(prev => [errorDetails, ...prev.slice(0, 49)]); // Keep last 50 errors
    });

    return unsubscribe;
  }, []);

  const clearErrors = React.useCallback(() => {
    setErrors([]);
  }, []);

  return {
    errors,
    clearErrors,
    errorCount: errors.length,
  };
}

export default NetworkErrorHandler;
