import React, { createContext, useContext, useState, ReactNode } from 'react';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

type BackendError = { detail?: string };

interface ErrorContextType {
  error: string | null;
  setError: (message: unknown) => void;
}

const ErrorContext = createContext<ErrorContextType>({ error: null, setError: () => {} });

// eslint-disable-next-line react-refresh/only-export-components
export const useError = (): ErrorContextType => useContext(ErrorContext);

export const ErrorProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [error, setErrorState] = useState<string | null>(null);
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
  };

  React.useEffect(() => {
    if (error) {
      toast.error(error, { position: 'bottom-right', autoClose: 5000 });
    }
  }, [error]);

  return (
    <ErrorContext.Provider value={{ error, setError }}>
      {children}
      <ToastContainer position="bottom-right" />
    </ErrorContext.Provider>
  );
};
