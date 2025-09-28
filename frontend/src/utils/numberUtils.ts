/**
 * Utility functions for formatting numeric values in the UI
 */

/**
 * Formats a numeric value for display with consistent decimal places
 * @param value - The numeric value to format
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted string or original value if not a number
 */
export function formatNumber(value: any, decimals: number = 2): string | any {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  
  const num = Number(value);
  if (isNaN(num)) {
    return value; // Return original value if it's not a number
  }
  
  return num.toFixed(decimals);
}

/**
 * Determines if a value should be formatted as a number
 * @param value - The value to check
 * @returns True if the value appears to be numeric
 */
export function isNumericValue(value: any): boolean {
  if (value === null || value === undefined || value === '') {
    return false;
  }
  
  return !isNaN(Number(value)) && isFinite(Number(value));
}

/**
 * Formats a value for display in data tiles
 * - Numbers are formatted to 2 decimal places
 * - Non-numbers are returned as-is
 * @param value - The value to format
 * @returns Formatted value for display
 */
export function formatDisplayValue(value: any): string {
  if (isNumericValue(value)) {
    return formatNumber(value, 2);
  }
  
  if (value === null || value === undefined) {
    return '—';
  }
  
  return String(value);
}

/**
 * Rounds a numeric value to specified decimal places while keeping it as a number
 * Used for chart data that needs to remain numeric for calculations
 * @param value - The numeric value to round
 * @param decimals - Number of decimal places (default: 2)
 * @returns Rounded number or original value if not numeric
 */
export function roundNumericValue(value: any, decimals: number = 2): any {
  if (isNumericValue(value)) {
    return Math.round(Number(value) * (10 ** decimals)) / (10 ** decimals);
  }
  return value;
}