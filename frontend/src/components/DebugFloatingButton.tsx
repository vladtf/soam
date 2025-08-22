import React, { useState, useEffect } from 'react';
import { Button, OverlayTrigger, Tooltip } from 'react-bootstrap';
import { FaBug } from 'react-icons/fa';
import DebugPanel from './DebugPanel';

const DebugFloatingButton: React.FC = () => {
  const [showPanel, setShowPanel] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  // Only show in development mode
  if ((import.meta as any).env?.MODE !== 'development') {
    return null;
  }

  // Listen for debug panel events
  useEffect(() => {
    const handleShowDebugPanel = () => {
      setShowPanel(true);
    };

    window.addEventListener('soam:show-debug-panel' as any, handleShowDebugPanel);

    return () => {
      window.removeEventListener('soam:show-debug-panel' as any, handleShowDebugPanel);
    };
  }, []);

  const buttonStyle: React.CSSProperties = {
    position: 'fixed',
    bottom: isMinimized ? '10px' : '20px',
    right: isMinimized ? '10px' : '20px',
    zIndex: 9998,
    borderRadius: '50%',
    width: isMinimized ? '40px' : '56px',
    height: isMinimized ? '40px' : '56px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    transition: 'all 0.3s ease',
    border: 'none',
    backgroundColor: '#dc3545',
    color: 'white',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const handleDoubleClick = () => {
    setIsMinimized(!isMinimized);
  };

  return (
    <>
      <OverlayTrigger
        placement="left"
        overlay={
          <Tooltip>
            Debug Panel
            <br />
            <small>Double-click to {isMinimized ? 'expand' : 'minimize'}</small>
          </Tooltip>
        }
      >
        <Button
          style={buttonStyle}
          onClick={() => setShowPanel(true)}
          onDoubleClick={handleDoubleClick}
          className="shadow-sm"
        >
          <FaBug size={isMinimized ? 16 : 20} />
        </Button>
      </OverlayTrigger>

      <DebugPanel show={showPanel} onHide={() => setShowPanel(false)} />
    </>
  );
};

export default DebugFloatingButton;
