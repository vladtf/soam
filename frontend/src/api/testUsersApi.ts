/** Test users API (development / testing). */
import { doFetch, getConfig } from './apiCore';

export interface TestUser {
  username: string;
  roles: string[];
  description: string;
  password: string;
}

export const getTestUsers = (): Promise<TestUser[]> => {
  const { backendUrl } = getConfig();
  return doFetch<TestUser[]>(`${backendUrl}/api/auth/test-users`, undefined, false);
};
