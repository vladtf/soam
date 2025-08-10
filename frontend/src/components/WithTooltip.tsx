import React from 'react';
import { OverlayTrigger, Tooltip } from 'react-bootstrap';

interface WithTooltipProps {
  tip: string;
  placement?: 'top' | 'bottom' | 'left' | 'right' | 'auto';
  className?: string;
  children: React.ReactElement;
}

const WithTooltip: React.FC<WithTooltipProps> = ({ tip, placement = 'top', className, children }) => {
  return (
    <OverlayTrigger
      placement={placement}
      delay={{ show: 300, hide: 100 }}
      overlay={<Tooltip>{tip}</Tooltip>}
    >
      <span className={className} style={{ display: 'inline-flex' }}>
        {children}
      </span>
    </OverlayTrigger>
  );
};

export default WithTooltip;
