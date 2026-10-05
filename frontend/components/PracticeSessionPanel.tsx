"use client";

import { useState, useEffect } from "react";
import { getPracticeQuestion, submitPracticeAnswer } from "../lib/api";
import type { PracticeQuestion } from "../lib/types";

interface Props {
  sessionId: string;
  busy: boolean;
  error: string;
  onFinish: () => void;
}

export default function PracticeSessionPanel({ sessionId, busy, error, onFinish }: Props) {
  const [question, setQuestion] = useState<PracticeQuestion | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);
  const [attemptNumber, setAttemptNumber] = useState(1);
  const [startTime, setStartTime] = useState<number>(Date.now());
  const [submitting, setSubmitting] = useState(false);

  const fetchNextQuestion = async () => {
    setLoading(true);
    setFetchError("");
    setSelectedAnswer(null);
    setIsCorrect(null);
    setAttemptNumber(1);
    try {
      const q = await getPracticeQuestion(sessionId);
      setQuestion(q);
      setStartTime(Date.now());
    } catch (err: any) {
      if (err.response?.status === 404) {
        setQuestion(null); // No more questions
      } else {
        setFetchError("Failed to load question. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNextQuestion();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleSubmit = async (index: number) => {
    if (submitting || isCorrect !== null) return;
    
    setSelectedAnswer(index);
    setSubmitting(true);
    const timeTaken = (Date.now() - startTime) / 1000;
    
    try {
      const result = await submitPracticeAnswer(sessionId, {
        question_id: question!.question_id,
        selected_answer: index,
        attempt_number: attemptNumber,
        time_taken_seconds: timeTaken,
      });
      
      setIsCorrect(result.is_correct);
      if (!result.is_correct) {
        setAttemptNumber(prev => prev + 1);
      }
    } catch (err) {
      setFetchError("Failed to submit answer.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="practice-panel">
      <span className="practice-index">SESSION OPEN</span>
      <span className="session-reference">Session · {sessionId.slice(-8)}</span>
      
      {(error || fetchError) && (
        <p className="form-error" role="alert">{error || fetchError}</p>
      )}

      {loading ? (
        <h3>Loading practice question...</h3>
      ) : question ? (
        <div className="question-block" style={{ marginTop: "1rem" }}>
          <h3>{question.question}</h3>
          <div className="options" style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "1rem" }}>
            {question.options.map((opt, i) => {
              let btnClass = "button button-outline";
              if (selectedAnswer === i) {
                if (isCorrect === true) btnClass = "button button-success";
                else if (isCorrect === false) btnClass = "button button-danger";
                else btnClass = "button button-dark";
              }
              
              return (
                <button
                  key={i}
                  className={btnClass}
                  onClick={() => handleSubmit(i)}
                  disabled={submitting || isCorrect === true}
                  style={{ textAlign: "left", opacity: isCorrect === true && selectedAnswer !== i ? 0.5 : 1 }}
                >
                  {opt}
                </button>
              );
            })}
          </div>
          
          {isCorrect !== null && (
            <div style={{ marginTop: "1rem", padding: "1rem", borderRadius: "8px", background: isCorrect ? "#ecfdf5" : "#fef2f2", color: isCorrect ? "#065f46" : "#991b1b" }}>
              <strong>{isCorrect ? "Correct!" : "Incorrect, try again."}</strong>
              {isCorrect && (
                <button 
                  className="button button-dark" 
                  style={{ marginTop: "1rem", width: "100%" }}
                  onClick={fetchNextQuestion}
                >
                  Next Question
                </button>
              )}
            </div>
          )}
        </div>
      ) : (
        <div style={{ marginTop: "2rem" }}>
          <h3>All practice questions completed!</h3>
          <p>You have finished the available practice material for this topic.</p>
          <button 
            className="button button-dark" 
            onClick={onFinish} 
            disabled={busy}
            style={{ marginTop: "1rem" }}
          >
            {busy ? "Closing session and gathering your record…" : "Close session and view my record"}<span>→</span>
          </button>
        </div>
      )}

      {question && (
        <button 
          className="button button-outline" 
          onClick={onFinish} 
          disabled={busy || submitting}
          style={{ marginTop: "2rem", width: "100%" }}
        >
          {busy ? "Closing session..." : "End Practice Session Early"}
        </button>
      )}
    </div>
  );
}
