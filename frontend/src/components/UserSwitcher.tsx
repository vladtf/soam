import React, { useState, useEffect } from 'react';
import { Dropdown, Badge, Spinner } from 'react-bootstrap';
import { FaUserCog, FaUser, FaUserShield, FaEye, FaExchangeAlt } from 'react-icons/fa';
import { toast } from 'react-toastify';
import { useAuth } from '../context/AuthContext';
import { getTestUsers, TestUser } from '../api/backendRequests';
import { logger } from '../utils/logger';

/**
 * UserSwitcher component for quickly switching between test users.
 * This is useful for testing role-based access control features.
 * 
 * Should only be visible in development mode.
 */
const UserSwitcher: React.FC = () => {
  const { user, login, logout, isAuthenticated } = useAuth();
  const [testUsers, setTestUsers] = useState<TestUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    loadTestUsers();
  }, []);

  const loadTestUsers = async () => {
    setLoading(true);
    try {
      const users = await getTestUsers();
      setTestUsers(users);
    } catch (error) {
      logger.warn('UserSwitcher', 'Failed to load test users', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchUser = async (testUser: TestUser) => {
    if (switching) return;
    
    setSwitching(true);
    try {
      // Logout current user first
      if (isAuthenticated) {
        logout();
      }
      
      // Login as selected test user
      await login(testUser.username, testUser.password);
      toast.success(`Switched to ${testUser.username} (${testUser.roles.join(', ')}) - Refreshing...`);
      
      // Refresh the page to ensure all data is reloaded with new user's permissions
      setTimeout(() => {
        window.location.reload();
      }, 500);
    } catch (error) {
      logger.error('UserSwitcher', 'Failed to switch user', error);
      toast.error(`Failed to switch to ${testUser.username}`);
      setSwitching(false);
    }
  };

  const getRoleIcon = (roles: string[]) => {
    if (roles.includes('admin')) return <FaUserShield className="text-danger" />;
    if (roles.includes('user')) return <FaUser className="text-primary" />;
    return <FaEye className="text-secondary" />;
  };

  const getRoleBadgeVariant = (role: string): string => {
    switch (role) {
      case 'admin': return 'danger';
      case 'user': return 'primary';
      case 'viewer': return 'secondary';
      default: return 'light';
    }
  };

  // Don't show if no test users available
  if (testUsers.length === 0 && !loading) {
    return null;
  }

  return (
    <Dropdown align="end">
      <Dropdown.Toggle
        variant="outline-warning"
        size="sm"
        id="user-switcher-dropdown"
        className="d-flex align-items-center gap-1"
        disabled={switching}
      >
        {switching ? (
          <Spinner animation="border" size="sm" />
        ) : (
          <>
            <FaExchangeAlt />
            <span className="d-none d-md-inline ms-1">Switch User</span>
          </>
        )}
      </Dropdown.Toggle>

      <Dropdown.Menu style={{ minWidth: '280px' }}>
        <Dropdown.Header>
          <FaUserCog className="me-2" />
          Test Users (Dev Mode)
        </Dropdown.Header>
        <Dropdown.Divider />

        {loading ? (
          <Dropdown.ItemText className="text-center py-2">
            <Spinner animation="border" size="sm" className="me-2" />
            Loading...
          </Dropdown.ItemText>
        ) : (
          <>
            {testUsers.map((testUser) => (
              <Dropdown.Item
                key={testUser.username}
                onClick={() => handleSwitchUser(testUser)}
                active={user?.username === testUser.username}
                className="py-2"
              >
                <div className="d-flex align-items-start gap-2">
                  <div className="mt-1">
                    {getRoleIcon(testUser.roles)}
                  </div>
                  <div className="flex-grow-1">
                    <div className="fw-bold">
                      {testUser.username}
                      {user?.username === testUser.username && (
                        <Badge bg="success" className="ms-2" pill>Current</Badge>
                      )}
                    </div>
                    <div className="small text-muted">{testUser.description}</div>
                    <div className="mt-1">
                      {testUser.roles.map((role) => (
                        <Badge
                          key={role}
                          bg={getRoleBadgeVariant(role)}
                          className="me-1"
                          style={{ fontSize: '0.7em' }}
                        >
                          {role}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </Dropdown.Item>
            ))}
          </>
        )}

        <Dropdown.Divider />
        <Dropdown.ItemText className="small text-muted">
          <FaUserCog className="me-1" />
          Password for all: <code>test123</code>
        </Dropdown.ItemText>
      </Dropdown.Menu>
    </Dropdown>
  );
};

export default UserSwitcher;
