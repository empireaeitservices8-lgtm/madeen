"use client";

import { useState } from "react";
import { login, saveToken, User } from "@/lib/api";
import { ShieldCheck, Eye, EyeOff, AlertCircle, Lock, User as UserIcon } from "lucide-react";

interface Props {
  onLogin: (user: User, token: string) => void;
}

export default function LoginPage({ onLogin }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await login(username, password);
      saveToken(res.access_token);
      onLogin(res.user, res.access_token);
    } catch (err) {
      setError((err as Error).message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-backdrop">
      <div className="login-card">
        <div className="login-brand">
          <div className="login-brand-icon"><ShieldCheck size={32} /></div>
          <h1>Site Compliance Hub</h1>
          <p>Sign in to access the compliance dashboard</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <div className="input-wrap">
              <UserIcon size={16} className="input-icon" />
              <input
                id="username"
                type="text"
                autoComplete="username"
                placeholder="admin"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="input-wrap">
              <Lock size={16} className="input-icon" />
              <input
                id="password"
                type={showPw ? "text" : "password"}
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="input-eye"
                onClick={() => setShowPw(!showPw)}
                tabIndex={-1}
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {error && (
            <div className="login-error">
              <AlertCircle size={15} />
              {error}
            </div>
          )}

          <button type="submit" className="btn-primary login-submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
