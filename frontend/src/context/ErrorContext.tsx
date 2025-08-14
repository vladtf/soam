import React, { createContext, useContext, useState, ReactNode } from 'react';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { reportClientError, startErrorQueueFlusher } from '../errors';
import ErrorCenter, { ErrorRecord } from '../components/ErrorCenter';

type BackendError = { detail?: string };

interface ErrorContextType {
  error: string | null;
  setError: (message: unknown) => void;
  openCenter: () => void;
}

const ErrorContext = createContext<ErrorContextType>({ error: null, setError: () => {}, openCenter: () => {} });

// eslint-disable-next-line react-refresh/only-export-components
export const useError = (): ErrorContextType => useContext(ErrorContext);

export const ErrorProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [error, setErrorState] = useState<string | null>(null);
  const [centerOpen, setCenterOpen] = useState(false);
  const [records, setRecords] = useState<ErrorRecord[]>([]);
  const [seq, setSeq] = useState(1);
  const setError = (err: unknown) => {
    let msg: string;
    if (typeof err === 'string') {
      msg = err;
    } else if (err instanceof Error) {
      msg = err.message;
    } else if (err && typeof err === 'object' && 'detail' in err) {
      msg = (err as BackendError).detail || JSON.stringify(err);
    } else {
      msg = JSON.stringify(err);
    }
    setErrorState(msg);
    // best-effort reporting
    reportClientError({ message: msg, severity: 'error' }).catch(() => {});
    setRecords((prev: ErrorRecord[]): ErrorRecord[] => [{ id: seq, message: msg, time: new Date(), severity: 'error' as const }, ...prev].slice(0, 100));
    setSeq((n) => n + 1);
  };

  React.useEffect(() => {
    startErrorQueueFlusher();
    if (error) {
      toast.error(error, { position: 'bottom-right', autoClose: 5000 });
    }
  }, [error]);

  return (
    <ErrorContext.Provider value={{ error, setError, openCenter: () => setCenterOpen(true) }}>
      {children}
      <ToastContainer position="bottom-right" />
      <ErrorCenter show={centerOpen} errors={records} onClose={() => setCenterOpen(false)} onClear={() => setRecords([])} />
    </ErrorContext.Provider>
  );
};
