import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Spinner, Container } from 'react-bootstrap';
import { useAuth, UserRole } from '../context/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  /** Required roles for access. If empty, any authenticated user can access. */
  requiredRoles?: UserRole[];
  /** Redirect path when not authenticated. Defaults to '/login'. */
  redirectTo?: string;
}

/**
 * ProtectedRoute wrapper that ensures user is authenticated before rendering children.
 * Optionally requires specific roles for access.
 * 
 * Usage:
 * ```tsx
 * <Route path="/admin" element={
 *   <ProtectedRoute requiredRoles={['admin']}>
 *     <AdminPage />
 *   </ProtectedRoute>
 * } />
 * ```
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requiredRoles = [],
  redirectTo = '/login' 
}) => {
  const { isAuthenticated, isLoading, hasRole } = useAuth();
  const location = useLocation();

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <Container className="d-flex justify-content-center align-items-center" style={{ minHeight: '60vh' }}>
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Checking authentication...</span>
        </Spinner>
      </Container>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to={redirectTo} state={{ from: location.pathname }} replace />;
  }

  // Check role requirements if specified
  if (requiredRoles.length > 0 && !hasRole(requiredRoles)) {
    // User is authenticated but doesn't have required role
    return (
      <Container className="py-5 text-center">
        <h2 className="text-danger mb-3">Access Denied</h2>
        <p className="text-muted">
          You don't have permission to access this page.
          <br />
          Required roles: {requiredRoles.join(', ')}
        </p>
      </Container>
    );
  }

  return <>{children}</>;
};

export default ProtectedRoute;
