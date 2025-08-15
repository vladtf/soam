import React from 'react';
// @ts-ignore - optional types
import ReactJson, { ReactJsonViewProps, ThemeKeys } from 'react-json-view';
import { useTheme } from '../context/ThemeContext';

interface ThemedReactJsonProps extends Omit<ReactJsonViewProps, 'theme'> {
  /**
   * Override the default theme behavior if needed
   */
  theme?: ThemeKeys | string;
}

const ThemedReactJson: React.FC<ThemedReactJsonProps> = ({ theme: overrideTheme, ...props }) => {
  const { theme } = useTheme();
  
  // Use override theme if provided, otherwise use context theme
  const jsonTheme = overrideTheme || (theme === 'dark' ? 'tomorrow' : 'rjv-default');
  
  return (
    <ReactJson 
      theme={jsonTheme as ThemeKeys}
      displayDataTypes={false}
      displayObjectSize={false}
      iconStyle="circle"
      indentWidth={2}
      enableClipboard={true}
      {...props}
    />
  );
};

export default ThemedReactJson;
