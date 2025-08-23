import { getConfig } from './config';

declare global {
  interface Window {
    __soam_lastReported?: Map<string, number>;
  }
}

export type ClientErrorPayload = {
  message: string;
  stack?: string;
  url?: string;
  component?: string;
  context?: string;
  severity?: 'debug' | 'info' | 'warn' | 'error' | 'fatal';
  user_agent?: string;
  session_id?: string;
  extra?: Record<string, unknown>;
};

const STORAGE_KEY = 'soam_error_queue_v2';
const LAST_FLUSH_KEY = 'soam_error_last_flush_ts';
const FLUSH_INTERVAL_MS = 5000; // throttle to at most once every 5s
const MAX_BATCH = 25; // safety cap per flush

// Feature flag (persisted) controlling whether client error reporting is active.
// Default is disabled (false) until the user opts in via UI.
const REPORTING_FLAG_KEY = 'soam_error_reporting_enabled';

export function isErrorReportingEnabled(): boolean {
  try {
    const v = localStorage.getItem(REPORTING_FLAG_KEY);
    return v === '1';
  } catch {
    return false;
  }
}

export function setErrorReportingEnabled(enabled: boolean): void {
  try { localStorage.setItem(REPORTING_FLAG_KEY, enabled ? '1' : '0'); } catch { /* ignore */ }
  try { window.dispatchEvent(new CustomEvent('soam:error-reporting-changed', { detail: { enabled } })); } catch { /* ignore */ }
  if (enabled) {
    // Kick off flusher if just enabled
    try { startErrorQueueFlusher(); } catch { /* ignore */ }
  }
}

function loadQueue(): ClientErrorPayload[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ClientErrorPayload[]) : [];
  } catch {
    return [];
  }
}

function saveQueue(queue: ClientErrorPayload[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
  } catch {
    // ignore storage failures
  }
}

export async function flushErrorQueue(force = false): Promise<void> {
  if (!isErrorReportingEnabled()) return; // skip entirely when disabled
  const now = Date.now();
  const last = Number(localStorage.getItem(LAST_FLUSH_KEY) || '0');
  if (!force && now - last < FLUSH_INTERVAL_MS) return; // respect throttle
  const queue = loadQueue();
  if (queue.length === 0) return;

  // Collapse identical messages (message+component+context+severity) keeping earliest extra data
  const dedupMap = new Map<string, ClientErrorPayload & { count: number }>();
  for (const item of queue) {
    const key = [item.message, item.component, item.context, item.severity].join('|');
    if (dedupMap.has(key)) {
      dedupMap.get(key)!.count += 1;
    } else {
      dedupMap.set(key, { ...item, count: 1 });
    }
  }
  // Prepare batch (limited)
  const batch = Array.from(dedupMap.values()).slice(0, MAX_BATCH).map(it => ({
    ...it,
    extra: { ...(it.extra || {}), occurrences: it.count },
  }));

  const { backendUrl } = getConfig();
  let successKeys = new Set<string>();
  try {
    // Send batch sequentially (could be parallel but keep simple & ordered)
    for (const entry of batch) {
      try {
        const res = await fetch(`${backendUrl}/api/errors/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...entry, user_agent: navigator.userAgent }),
        });
        if (res.ok) {
          const k = [entry.message, entry.component, entry.context, entry.severity].join('|');
          successKeys.add(k);
        }
      } catch {
        // leave in queue
      }
    }
  } finally {
    // Rebuild remaining queue excluding successes (only one occurrence per success key removed per original count)
    const newQueue: ClientErrorPayload[] = [];
    const countsConsumed: Record<string, number> = {};
    for (const item of queue) {
      const key = [item.message, item.component, item.context, item.severity].join('|');
      if (successKeys.has(key)) {
        countsConsumed[key] = (countsConsumed[key] || 0) + 1;
        const total = dedupMap.get(key)?.count || 0;
        // Remove all occurrences if at least one success (since batch included aggregated count)
        if (countsConsumed[key] >= total) {
          continue;
        } else {
          continue; // we aggregated; drop duplicates
        }
      } else {
        newQueue.push(item);
      }
    }
    saveQueue(newQueue);
    localStorage.setItem(LAST_FLUSH_KEY, String(Date.now()));
  }
}

export async function reportClientError(payload: ClientErrorPayload): Promise<void> {
  if (!isErrorReportingEnabled()) return; // feature disabled
  // Suppress noisy repeats (in-memory) for a cooldown window
  const SUPPRESS_WINDOW_MS = 60000; // 1 minute per unique key
  const key = [payload.message, payload.component, payload.context, payload.severity].join('|');
  const now = Date.now();
  const lastReportedMap: Map<string, number> = window.__soam_lastReported || new Map<string, number>();
  if (!window.__soam_lastReported) { window.__soam_lastReported = lastReportedMap; }
  const lastTs = lastReportedMap.get(key) || 0;
  if (now - lastTs < SUPPRESS_WINDOW_MS) {
    return; // skip enqueue; already recently reported
  }
  lastReportedMap.set(key, now);

  // Always enqueue; rely on batch flusher + dedup for consolidation
  const q = loadQueue();
  q.push(payload);
  saveQueue(q);
  flushErrorQueue(false).catch(() => {}); // throttled inside
}

// Try to flush on visibility changes and on interval
let started = false;
export function startErrorQueueFlusher(): void {
  if (started) return;
  if (!isErrorReportingEnabled()) return; // don't start if disabled (will be retried on enable)
  started = true;
  const tick = () => { try { flushErrorQueue(); } catch { /* ignore */ } };
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') tick();
  });
  window.addEventListener('online', () => flushErrorQueue(true));
  // Frequent lightweight check; throttling inside flush prevents overposting
  setInterval(tick, 1000);
}


