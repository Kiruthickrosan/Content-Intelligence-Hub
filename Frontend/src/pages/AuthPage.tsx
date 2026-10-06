import { Link, useNavigate } from "@tanstack/react-router";
import { motion } from "motion/react";
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail, User } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Logo } from "../components/common/UI";
import { useAuth } from "../context/AuthContext";
export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const loginMode = mode === "login",
    auth = useAuth(),
    go = useNavigate(),
    [show, setShow] = useState(false),
    [busy, setBusy] = useState(false),
    [f, setF] = useState({ username: "", email: "", password: "" });
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      loginMode
        ? await auth.login(f.username, f.password)
        : await auth.register(f.username, f.email, f.password);
      toast.success(loginMode ? "Welcome back" : "Your account is ready");
      void go({ to: "/dashboard" });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Unable to continue");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <section className="auth-aside">
        <Logo />
        <div className="auth-copy">
          <span className="eyebrow light">Your video knowledge, searchable</span>
          <h1>Turn every video into an answer.</h1>
          <p>
            Connect channels, index spoken knowledge, and get precise answers grounded in the
            content you trust.
          </p>
          <div className="signal-card">
            <span>✦</span>
            <div>
              <strong>Answers with evidence</strong>
              <small>Every response links back to the exact source.</small>
            </div>
          </div>
        </div>
        <small>Built for teams who learn from video.</small>
      </section>
      <section className="auth-form-wrap">
        <motion.div
          className="auth-form-card"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="mobile-logo">
            <Logo />
          </div>
          <span className="eyebrow">{loginMode ? "Welcome back" : "Create your workspace"}</span>
          <h2>{loginMode ? "Sign in to YouTube Q&A" : "Start building your knowledge base"}</h2>
          <p>
            {loginMode ? "Continue where you left off." : "Create an account in under a minute."}
          </p>
          <form onSubmit={submit}>
            <label>
              Username
              <div className="input-shell">
                <User />
                <input
                  required
                  minLength={3}
                  value={f.username}
                  onChange={(e) => setF({ ...f, username: e.target.value })}
                  placeholder="your_username"
                />
              </div>
            </label>
            {!loginMode && (
              <label>
                Email
                <div className="input-shell">
                  <Mail />
                  <input
                    required
                    type="email"
                    value={f.email}
                    onChange={(e) => setF({ ...f, email: e.target.value })}
                    placeholder="you@example.com"
                  />
                </div>
              </label>
            )}
            <label>
              Password
              <div className="input-shell">
                <LockKeyhole />
                <input
                  required
                  minLength={loginMode ? 1 : 8}
                  type={show ? "text" : "password"}
                  value={f.password}
                  onChange={(e) => setF({ ...f, password: e.target.value })}
                  placeholder={loginMode ? "Enter your password" : "At least 8 characters"}
                />
                <button type="button" onClick={() => setShow(!show)}>
                  {show ? <EyeOff /> : <Eye />}
                </button>
              </div>
            </label>
            <button className="btn btn-primary btn-block" disabled={busy}>
              {busy ? (
                "Please wait…"
              ) : (
                <>
                  {loginMode ? "Sign in" : "Create account"}
                  <ArrowRight />
                </>
              )}
            </button>
          </form>
          <p className="auth-switch">
            {loginMode ? "New here? " : "Already registered? "}
            <Link to={loginMode ? "/register" : "/login"}>
              {loginMode ? "Create an account" : "Sign in"}
            </Link>
          </p>
        </motion.div>
      </section>
    </main>
  );
}
