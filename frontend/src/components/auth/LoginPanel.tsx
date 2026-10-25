import { useState, type FormEvent } from "react";
import { useAuth } from "../../context/AuthContext";

interface LoginPanelProps {
  title?: string;
  subtitle?: string;
}

export default function LoginPanel({
  title = "Municipal Authentication Required",
  subtitle = "Stage D budget optimization and intervention selection require Planner or Admin privileges.",
}: LoginPanelProps) {
  const {
    user,
    role,
    isAuthenticated,
    isPlannerOrAdmin,
    login,
    logout,
    loginError,
    sessionMessage,
    isLoading,
  } = useAuth();

  // Typed by the user: strictly empty initial values, autocomplete off
  const [username, setUsername] = useState<string>("");
  const [password, setPassword] = useState<string>("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    await login(username.trim(), password);
  };

  // If already logged in but with insufficient role (e.g., public or researcher)
  if (isAuthenticated && user && !isPlannerOrAdmin) {
    return (
      <div className="mx-auto max-w-xl rounded-xl border border-amber-200 bg-amber-50 p-6 shadow-sm">
        <div className="flex items-center justify-between pb-4 border-b border-amber-200">
          <div>
            <h3 className="text-lg font-semibold text-amber-900">Restricted Privileges</h3>
            <p className="text-sm text-amber-700">Role '{role}' is not authorized for budget optimization.</p>
          </div>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-200 text-amber-900 uppercase">
            {role}
          </span>
        </div>

        <div className="mt-4 text-sm text-amber-800 space-y-2">
          <p>
            You are signed in as <strong>{user.username}</strong> ({user.email}).
          </p>
          <p>
            Municipal optimization requires <strong>Planner</strong> or <strong>Admin</strong> privileges.
            Please sign out and log in with an authorized municipal account.
          </p>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={logout}
            className="px-4 py-2 text-sm font-medium text-amber-900 bg-amber-200 hover:bg-amber-300 rounded-lg transition"
          >
            Sign Out & Switch Account
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg rounded-xl border border-slate-200 bg-white p-8 shadow-card">
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <span className="h-2 w-2 rounded-full bg-indigo-700"></span>
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Access Control
          </span>
        </div>
        <h3 className="text-xl font-bold text-slate-900">{title}</h3>
        <p className="text-sm text-slate-600 mt-1">{subtitle}</p>
      </div>

      {sessionMessage && (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
        >
          {sessionMessage}
        </div>
      )}

      {loginError && (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
        >
          {loginError}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="auth-username"
            className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1"
          >
            Username
          </label>
          <input
            id="auth-username"
            type="text"
            autoComplete="off"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={isLoading}
            placeholder="Municipal username (e.g. planner_officer)"
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-600/30"
            required
          />
        </div>

        <div>
          <label
            htmlFor="auth-password"
            className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1"
          >
            Password
          </label>
          <input
            id="auth-password"
            type="password"
            autoComplete="off"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isLoading}
            placeholder="Account password"
            className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-600/30"
            required
          />
        </div>

        <button
          type="submit"
          disabled={isLoading || !username.trim() || !password}
          className="w-full rounded-lg bg-indigo-700 py-2.5 px-4 text-sm font-semibold text-white shadow-xs hover:bg-indigo-800 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300 transition"
        >
          {isLoading ? "Authenticating..." : "Sign In to Access Optimization"}
        </button>
      </form>

      <div className="mt-6 border-t border-slate-100 pt-4 text-xs text-slate-500">
        <p className="font-semibold text-slate-600 mb-1">Municipal Role Accounts:</p>
        <p>
          Authoritative roles: <code>planner_officer</code> (Planner) or <code>smc_admin</code> (Admin).
          Authentication tokens are held strictly in memory during active browser sessions.
        </p>
      </div>
    </div>
  );
}
