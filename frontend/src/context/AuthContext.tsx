import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { loginAuth, type AuthUser, type UserRole } from "../services/authApi";

export interface AuthContextType {
  token: string | null;
  user: AuthUser | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  isPlannerOrAdmin: boolean;
  loginError: string | null;
  sessionMessage: string | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  clearSession: (reason?: string) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  // STRICT INVARIANT: Token and User stored strictly in in-memory React state.
  // Never written to localStorage, sessionStorage, cookies, or URL.
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [sessionMessage, setSessionMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const clearSession = useCallback((reason?: string) => {
    setToken(null);
    setUser(null);
    if (reason) {
      setSessionMessage(reason);
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setLoginError(null);
    setSessionMessage(null);
  }, []);

  const login = useCallback(
    async (username: string, password: string): Promise<boolean> => {
      setIsLoading(true);
      setLoginError(null);
      setSessionMessage(null);
      try {
        const data = await loginAuth(username, password);
        setToken(data.access_token);
        setUser(data.user);
        setLoginError(null);
        setSessionMessage(null);
        return true;
      } catch (err: unknown) {
        setToken(null);
        setUser(null);
        const msg =
          err instanceof Error
            ? err.message
            : "Authentication failed. Please verify credentials.";
        setLoginError(msg);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const role = user?.role ?? null;
  const isAuthenticated = token !== null && user !== null;
  const isPlannerOrAdmin = role === "planner" || role === "admin";

  const contextValue = useMemo<AuthContextType>(
    () => ({
      token,
      user,
      role,
      isAuthenticated,
      isPlannerOrAdmin,
      loginError,
      sessionMessage,
      isLoading,
      login,
      logout,
      clearSession,
    }),
    [
      token,
      user,
      role,
      isAuthenticated,
      isPlannerOrAdmin,
      loginError,
      sessionMessage,
      isLoading,
      login,
      logout,
      clearSession,
    ]
  );

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
