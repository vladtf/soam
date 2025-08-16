/**
 * Formats a date as relative time (e.g., "5 minutes ago", "just now")
 */
export const formatRelativeTime = (date: Date): string => {
  const now = new Date();
  const diffInMs = now.getTime() - date.getTime();
  const diffInSeconds = Math.floor(diffInMs / 1000);
  const diffInMinutes = Math.floor(diffInSeconds / 60);
  const diffInHours = Math.floor(diffInMinutes / 60);
  const diffInDays = Math.floor(diffInHours / 24);

  if (diffInSeconds < 30) {
    return 'just now';
  } else if (diffInSeconds < 60) {
    return `${diffInSeconds} seconds ago`;
  } else if (diffInMinutes === 1) {
    return '1 minute ago';
  } else if (diffInMinutes < 60) {
    return `${diffInMinutes} minutes ago`;
  } else if (diffInHours === 1) {
    return '1 hour ago';
  } else if (diffInHours < 24) {
    return `${diffInHours} hours ago`;
  } else if (diffInDays === 1) {
    return '1 day ago';
  } else {
    return `${diffInDays} days ago`;
  }
};

/**
 * Formats refresh period in a human-readable way (e.g., "every 30 seconds", "every 5 minutes")
 */
export const formatRefreshPeriod = (intervalMs: number): string => {
  const seconds = Math.floor(intervalMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (seconds < 60) {
    return seconds === 1 ? 'every second' : `every ${seconds} seconds`;
  } else if (minutes < 60) {
    return minutes === 1 ? 'every minute' : `every ${minutes} minutes`;
  } else {
    return hours === 1 ? 'every hour' : `every ${hours} hours`;
  }
};
