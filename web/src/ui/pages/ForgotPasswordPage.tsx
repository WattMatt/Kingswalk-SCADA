// web/src/ui/pages/ForgotPasswordPage.tsx
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/core/api-client";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await apiClient.forgotPassword(email);
    } finally {
      // Always show success — never reveal whether email is registered
      setSubmitted(true);
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950">
      <div className="w-full max-w-sm rounded-xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
        <h1 className="mb-2 text-xl font-semibold text-white">Reset Password</h1>
        {submitted ? (
          <div>
            <p className="mb-4 text-sm text-slate-300">
              If that email is registered, a reset link has been sent. Check your inbox.
            </p>
            <Link
              to="/login"
              className="text-sm text-blue-400 hover:text-blue-300"
            >
              Back to login
            </Link>
          </div>
        ) : (
          <>
            <p className="mb-6 text-sm text-slate-400">
              Enter your email and we'll send a reset link.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="email" className="mb-1 block text-sm text-slate-300">
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
                  placeholder="you@example.com"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
              >
                {loading ? "Sending…" : "Send reset link"}
              </button>
            </form>
            <Link
              to="/login"
              className="mt-4 block text-center text-sm text-slate-500 hover:text-slate-400"
            >
              Back to login
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
