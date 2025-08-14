import { getConfig } from './config';

type ClientErrorPayload = {
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

const STORAGE_KEY = 'soam_error_queue_v1';

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

export async function flushErrorQueue(): Promise<void> {
  const queue = loadQueue();
  if (queue.length === 0) return;
  const { backendUrl } = getConfig();
  const remaining: ClientErrorPayload[] = [];
  for (const item of queue) {
    try {
      const res = await fetch(`${backendUrl}/errors/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...item, user_agent: navigator.userAgent }),
      });
      if (!res.ok) remaining.push(item);
    } catch {
      remaining.push(item);
    }
  }
  if (remaining.length !== queue.length) {
    saveQueue(remaining);
  }
}

export async function reportClientError(payload: ClientErrorPayload): Promise<void> {
  const { backendUrl } = getConfig();
  try {
    const res = await fetch(`${backendUrl}/errors/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, user_agent: navigator.userAgent }),
    });
    if (!res.ok) throw new Error('Failed to send');
  } catch {
    const q = loadQueue();
    q.push(payload);
    saveQueue(q);
  }
}

// Try to flush on visibility changes and on interval
let started = false;
export function startErrorQueueFlusher(): void {
  if (started) return;
  started = true;
  const tick = () => {
    try { flushErrorQueue(); } catch { /* ignore */ }
  };
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') tick();
  });
  window.addEventListener('online', tick);
  setInterval(tick, 15000);
}


