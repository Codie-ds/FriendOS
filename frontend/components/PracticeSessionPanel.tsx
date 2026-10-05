"use client";

interface Props {
  sessionId: string;
  busy: boolean;
  error: string;
  onFinish: () => void;
}

/**
 * Practice UI integration boundary. The current API can open and close a
 * learning session, but supplies no client-safe practice questions or
 * authoritative practice-answer evaluation. Connect those capabilities here
 * when a practice API becomes available.
 */
export default function PracticeSessionPanel({ sessionId, busy, error, onFinish }: Props) {
  return (
    <div className="practice-panel">
      <span className="practice-index">SESSION OPEN</span>
      <h3>Practice engine is being prepared.</h3>
      <p>The learning session is active, but practice questions and answer evaluation are not available yet. FriendOS won’t record answers or behavior it can’t verify.</p>
      <span className="session-reference">Session · {sessionId.slice(-8)}</span>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="button button-dark" onClick={onFinish} disabled={busy}>{busy ? "Closing session and gathering your record…" : "Close session and view my record"}<span>→</span></button>
    </div>
  );
}
