import React from 'react';
import { Table, TableProps } from 'react-bootstrap';
import { useTheme } from '../context/ThemeContext';

type Props = TableProps & { children: React.ReactNode };

const ThemedTable: React.FC<Props> = ({ children, variant, ...rest }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const effectiveVariant = variant ?? (isDark ? 'dark' : undefined);
  return (
    <Table variant={effectiveVariant} {...rest}>
      {children}
    </Table>
  );
};

export default ThemedTable;
