/**
 * Utility functions for handling and formatting error messages from API responses
 */

/**
 * Extracts a user-friendly error message from an error object
 * Handles various error formats including network errors with response details
 * 
 * @param error - The error object from a failed API call
 * @param defaultMessage - Default message to use if no specific message can be extracted
 * @returns A clean, user-friendly error message
 */
export function extractErrorMessage(error: unknown, defaultMessage: string = 'An error occurred'): string {
  let errorMessage = defaultMessage;
  
  if (error instanceof Error) {
    // Check if it's a network error with response details
    const networkError = error as any;
    if (networkError.response?.detail) {
      errorMessage = networkError.response.detail;
    } else if (error.message) {
      errorMessage = error.message;
    }
  }
  
  // Remove any HTTP status code prefixes (like "409: ", "400: ", etc.)
  errorMessage = errorMessage.replace(/^\d+:\s*/, '');
  
  return errorMessage;
}

/**
 * Extracts error message for computation-related operations
 */
export function extractComputationErrorMessage(error: unknown): string {
  return extractErrorMessage(error, 'Failed to perform computation operation');
}

/**
 * Extracts error message for dashboard tile operations
 */
export function extractDashboardTileErrorMessage(error: unknown): string {
  return extractErrorMessage(error, 'Failed to perform dashboard tile operation');
}

/**
 * Extracts error message for preview operations
 */
export function extractPreviewErrorMessage(error: unknown): string {
  return extractErrorMessage(error, 'Failed to preview data');
}

/**
 * Extracts error message for delete operations
 */
export function extractDeleteErrorMessage(error: unknown): string {
  return extractErrorMessage(error, 'Failed to delete item');
}
