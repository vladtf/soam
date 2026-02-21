/**
 * Centralized frontend logger for consistent, structured logging.
 *
 * Usage:
 *   import { logger } from '../utils/logger';
 *   logger.info('DataSourcesPage', 'Source created', { id: 123 });
 *   logger.error('usePipelineData', 'Failed to load devices', error);
 *   logger.warn('MinioBrowser', 'Preload skipped');
 *   logger.debug('TileWithData', 'Refresh tick', { tileId });
 *
 * All output is suppressed in production builds automatically.
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const isDev = (): boolean => {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (import.meta as any).env?.MODE === 'development';
  } catch {
    return false;
  }
};

const EMOJI: Record<LogLevel, string> = {
  debug: '🔍',
  info: '✅',
  warn: '⚠️',
  error: '❌',
};

function formatMsg(level: LogLevel, component: string, message: string): string {
  return `${EMOJI[level]} [${component}] ${message}`;
}

/**
 * Structured logger that mirrors the backend emoji‑prefix convention.
 * In production only 'warn' and 'error' are emitted. Everything else is a no‑op.
 */
export const logger = {
  /** Debug‑level logging (dev only). */
  debug(component: string, message: string, data?: unknown): void {
    if (!isDev()) return;
    if (data !== undefined) {
      console.debug(formatMsg('debug', component, message), data);
    } else {
      console.debug(formatMsg('debug', component, message));
    }
  },

  /** Informational logging (dev only). */
  info(component: string, message: string, data?: unknown): void {
    if (!isDev()) return;
    if (data !== undefined) {
      console.log(formatMsg('info', component, message), data);
    } else {
      console.log(formatMsg('info', component, message));
    }
  },

  /** Warnings — always emitted. */
  warn(component: string, message: string, data?: unknown): void {
    if (data !== undefined) {
      console.warn(formatMsg('warn', component, message), data);
    } else {
      console.warn(formatMsg('warn', component, message));
    }
  },

  /** Errors — always emitted. */
  error(component: string, message: string, error?: unknown): void {
    if (error !== undefined) {
      console.error(formatMsg('error', component, message), error);
    } else {
      console.error(formatMsg('error', component, message));
    }
  },
};

/**
 * Convenience: returns true when running in Vite dev mode.
 * Use this instead of scattering `(import.meta as any).env?.MODE === 'development'` everywhere.
 */
export { isDev };
