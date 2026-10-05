"use client";

import { FormEvent, useMemo, useState } from "react";
import {
  completeLearningSession,
  getHistory,
  getLearnerSummary,
  getRecommendation,
  onboardLearner,
  startDiagnostic,
  startLearningSession,
  submitDiagnostic,
  uploadMaterial,
} from "@/lib/api";
import type {
  AdaptiveRecommendation,
  ClientQuestion,
  HistoryEntry,
  LearnerBehaviorSummary,
  Topic,
  TopicScore,
} from "@/lib/types";
import PracticeSessionPanel from "@/components/PracticeSessionPanel";

type Stage = "onboarding" | "upload" | "diagnostic" | "baseline" | "practice" | "review";

const loop = [
  ["PLAN", "Start with a baseline grounded in your diagnostic."],
  ["ACT", "Practice with learning material, at your own pace."],
  ["OBSERVE", "Capture real learning actions when practice is available."],
  ["LEARN", "Use measured evidence to understand what is working."],
  ["ADAPT", "Choose a next step informed by your learning record."],
];

function jumpTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function SectionHeading({ number, eyebrow, title, detail }: { number: string; eyebrow: string; title: string; detail?: string }) {
  return (
    <div className="section-heading">
      <span className="section-number">{number}</span>
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="display-title">{title}</h2>
        {detail && <p className="section-detail">{detail}</p>}
      </div>
    </div>
  );
}

function ErrorNote({ children }: { children: string }) {
  return <p className="form-error" role="alert">{children}</p>;
}

export default function JourneyExperience() {
  const [stage, setStage] = useState<Stage>("onboarding");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [knownTopics, setKnownTopics] = useState("");
  const [learnerId, setLearnerId] = useState("");
  const [materialId, setMaterialId] = useState("");
  const [materialTitle, setMaterialTitle] = useState("");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [questions, setQuestions] = useState<ClientQuestion[]>([]);
  const [diagnosticSessionId, setDiagnosticSessionId] = useState("");
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number | null>>({});
  const [topicScores, setTopicScores] = useState<TopicScore[]>([]);
  const [skillProfile, setSkillProfile] = useState<Record<string, number>>({});
  const [learningSessionId, setLearningSessionId] = useState("");
  const [sessionCompleted, setSessionCompleted] = useState(false);
  const [summary, setSummary] = useState<LearnerBehaviorSummary | null>(null);
  const [recommendation, setRecommendation] = useState<AdaptiveRecommendation | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  const weakestTopic = useMemo(() => {
    if (topicScores.length) return [...topicScores].sort((a, b) => a.score - b.score)[0].topic;
    return topics[0]?.name ?? "";
  }, [topicScores, topics]);

  function advance(next: Stage, anchor: string) {
    setStage(next);
    setError("");
    window.setTimeout(() => jumpTo(anchor), 50);
  }

  async function handleOnboard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const response = await onboardLearner({
        name: name.trim(),
        learning_goal: goal.trim(),
        known_topics: knownTopics.split(",").map((topic) => topic.trim()).filter(Boolean),
        weak_topics: [],
      });
      if (!response.success) throw new Error("FriendOS could not create your learner profile.");
      setLearnerId(response.learner_id);
      advance("upload", "upload");
    } catch {
      setError("We couldn’t save your details. Check the API connection and try again.");
    } finally { setBusy(false); }
  }

  async function handleUpload(file?: File) {
    if (!file) return;
    setError("");
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setError("Choose a PDF file to continue."); return;
    }
    setBusy(true);
    try {
      const response = await uploadMaterial(file);
      if (!response.success) throw new Error("PDF analysis did not complete.");
      setMaterialId(response.material_id);
      setMaterialTitle(response.title);
      setTopics(response.topics);
      advance("diagnostic", "diagnostic");
    } catch {
      setError("We couldn’t analyze that PDF. Try another text-based PDF or check the API connection.");
    } finally { setBusy(false); }
  }

  async function beginDiagnostic() {
    setBusy(true); setError("");
    try {
      const response = await startDiagnostic({ learner_id: learnerId, material_id: materialId });
      if (!response.success || response.questions.length === 0) throw new Error("No diagnostic questions were returned.");
      setDiagnosticSessionId(response.session_id);
      setQuestions(response.questions);
      setAnswers({}); setQuestionIndex(0);
    } catch {
      setError("The diagnostic couldn’t be loaded. Please try again.");
    } finally { setBusy(false); }
  }

  async function submitAssessment() {
    setBusy(true); setError("");
    try {
      const response = await submitDiagnostic(diagnosticSessionId, questions.map((question) => ({
        question_id: question.question_id,
        selected_answer: answers[question.question_id] ?? null,
      })));
      if (!response.success) throw new Error("Diagnostic submission failed.");
      setTopicScores(response.topic_scores);
      setSkillProfile(response.skill_profile);
      advance("baseline", "baseline");
    } catch {
      setError("Your answers couldn’t be submitted. Please try again.");
    } finally { setBusy(false); }
  }

  async function beginLearning() {
    if (!weakestTopic) { setError("No topic is available to start a learning session."); return; }
    setBusy(true); setError("");
    try {
      const response = await startLearningSession({ learner_id: learnerId, material_id: materialId, topic: weakestTopic });
      if (!response.success) throw new Error("Session could not be started.");
      setLearningSessionId(response.session_id);
      advance("practice", "practice");
    } catch {
      setError("The learning session couldn’t be started. Please try again.");
    } finally { setBusy(false); }
  }

  async function finishSession() {
    setBusy(true); setError("");
    try {
      if (!sessionCompleted) {
        await completeLearningSession(learningSessionId);
        setSessionCompleted(true);
      }
      const recommendationResponse = await getRecommendation({ learner_id: learnerId, material_id: materialId });
      const [summaryResponse, historyResponse] = await Promise.all([
        getLearnerSummary(learnerId),
        getHistory(learnerId),
      ]);
      setSummary(summaryResponse);
      setRecommendation(recommendationResponse.recommendation);
      setHistory(historyResponse.history);
      advance("review", "review");
    } catch {
      setError("We couldn’t load the latest summary or adaptation. Try finishing again; please check the API connection.");
    } finally { setBusy(false); }
  }

  const activeQuestion = questions[questionIndex];

  return (
    <main>
      <header className="site-header">
        <a className="wordmark" href="#top" aria-label="FriendOS home">FriendOS<span>®</span></a>
        <nav aria-label="Main navigation"><a href="#approach">Approach</a><a href="#journey">Your journey</a></nav>
        <a className="header-link" href="#journey">Begin <span aria-hidden="true">↘</span></a>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><i /> A learning companion that pays attention</p>
          <h1 className="hero-title">Learning that<br />moves <em>with you.</em></h1>
          <p className="hero-intro">A clearer way to learn from the material you already have. Start with what you know; take the next step with evidence.</p>
          <button className="button button-dark" onClick={() => jumpTo("journey")}>Begin your learning journey <span>↘</span></button>
          <p className="hero-caption">A considered pace. A path shaped around you.</p>
        </div>
        <div className="hero-art" aria-label="An abstract editorial illustration of a learning path">
          <div className="art-index">FIELD NOTES&nbsp;&nbsp; / &nbsp;&nbsp;01</div>
          <div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
          <div className="art-vertical" /><div className="art-dot dot-one" /><div className="art-dot dot-two" />
          <span className="art-word art-plan">PLAN</span><span className="art-word art-adapt">ADAPT</span>
          <span className="art-mark">F</span>
          <p className="art-note">A learning path<br />is never a straight line.</p>
        </div>
        <div className="hero-foot"><span>INDEPENDENT LEARNING, RECONSIDERED</span><span>01 — 05</span></div>
      </section>

      <section className="approach" id="approach">
        <div className="approach-intro"><p className="eyebrow">The FriendOS method</p><h2 className="display-title">A learning loop,<br /><em>made personal.</em></h2><p>Good learning is a practice of noticing. FriendOS starts with a plan, pays attention to the work, and helps you find a useful next step.</p></div>
        <div className="loop-list">
          {loop.map(([word, text], index) => <div className="loop-row" key={word}><span className="loop-index">0{index + 1}</span><h3>{word}</h3><p>{text}</p><span className="loop-arrow">↗</span></div>)}
        </div>
        <div className="approach-note"><span className="note-rule" /><p>PLAN <b>→</b> ACT <b>→</b> OBSERVE <b>→</b> LEARN <b>→</b> ADAPT</p><span className="eyebrow">A continuous practice</span></div>
      </section>

      <section className="journey" id="journey">
        <div className="journey-topline"><span className="eyebrow">Your learning journey</span><span className="eyebrow">{stage === "review" ? "COMPLETE" : "IN PROGRESS"}</span></div>
        <div className="journey-grid">
          <aside className="journey-aside"><p className="eyebrow">A thoughtful beginning</p><h2 className="display-title">Start where<br />you <em>are.</em></h2><p>Bring a goal and a piece of study material. We’ll establish a real baseline together.</p><div className="aside-stamp">YOUR<br />OWN<br /><i>PACE</i></div></aside>
          <div className="journey-content">
            <section className="journey-step" id="onboarding">
              <SectionHeading number="01" eyebrow="A little context" title="What brings you here?" detail="A name and a learning goal are enough to begin." />
              {stage === "onboarding" ? <form className="form-stack" onSubmit={handleOnboard}>
                <label>Your name<input className="text-field" value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" placeholder="How should we address you?" required /></label>
                <label>What would you like to learn?<input className="text-field" value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="A subject, skill, or question" required /></label>
                <label>Topics you already know <span className="optional">OPTIONAL · SEPARATE WITH COMMAS</span><input className="text-field" value={knownTopics} onChange={(event) => setKnownTopics(event.target.value)} placeholder="For example, the fundamentals" /></label>
                {error && <ErrorNote>{error}</ErrorNote>}
                <button className="button button-dark" disabled={busy}>{busy ? "Saving your details…" : "Continue to your material"}<span>→</span></button>
              </form> : <CompletedLine title={`Welcome${name ? `, ${name}` : ""}.`} detail="Your learner profile is ready." />}
            </section>

            {stage !== "onboarding" && <section className="journey-step" id="upload">
              <SectionHeading number="02" eyebrow="Bring your material" title="A document to learn from." detail="Upload a text-based PDF. FriendOS will identify its topics." />
              {stage === "upload" ? <div className="upload-box"><label className="upload-control"><span className="upload-icon">↑</span><strong>{busy ? "Reading your material…" : "Choose a PDF to begin"}</strong><span>PDF · up to 10 MB</span><input type="file" accept="application/pdf,.pdf" disabled={busy} onChange={(event) => void handleUpload(event.target.files?.[0])} /></label>{error && <ErrorNote>{error}</ErrorNote>}</div> : <><CompletedLine title={materialTitle || "Material analyzed"} detail="Topics identified from your document." /><div className="topic-chips">{topics.map((topic) => <span key={topic.name}>{topic.name}<small>{topic.difficulty}</small></span>)}</div></>}
            </section>}

            {stage !== "onboarding" && stage !== "upload" && <section className="journey-step" id="diagnostic">
              <SectionHeading number="03" eyebrow="Establish a baseline" title="What do you know already?" detail="A short diagnostic gives us a real starting point. Your answers are evaluated by the backend." />
              {stage === "diagnostic" && questions.length === 0 ? <div className="inline-action">{error && <ErrorNote>{error}</ErrorNote>}<button className="button button-outline" onClick={() => void beginDiagnostic()} disabled={busy}>{busy ? "Preparing diagnostic…" : "Begin diagnostic"}<span>→</span></button></div> : stage === "diagnostic" && activeQuestion ? <div className="question-panel">
                <div className="question-meta"><span>{activeQuestion.topic}</span><span>{questionIndex + 1} / {questions.length}</span></div>
                <div className="progress-track"><div className="progress-fill" style={{ width: `${((questionIndex + 1) / questions.length) * 100}%` }} /></div>
                <h3>{activeQuestion.question}</h3>
                <div className="answer-list">{activeQuestion.options.map((option, index) => <button className={`answer-option ${answers[activeQuestion.question_id] === index ? "selected" : ""}`} key={`${activeQuestion.question_id}-${index}`} onClick={() => setAnswers((previous) => ({ ...previous, [activeQuestion.question_id]: index }))}><span>{String.fromCharCode(65 + index)}</span>{option}</button>)}</div>
                {error && <ErrorNote>{error}</ErrorNote>}
                <div className="question-actions"><button className="text-button" onClick={() => { setAnswers((previous) => ({ ...previous, [activeQuestion.question_id]: null })); if (questionIndex < questions.length - 1) setQuestionIndex(questionIndex + 1); else void submitAssessment(); }}>Skip this question</button><button className="button button-dark" disabled={busy} onClick={() => { if (questionIndex < questions.length - 1) setQuestionIndex(questionIndex + 1); else void submitAssessment(); }}>{busy ? "Submitting…" : questionIndex === questions.length - 1 ? "Submit diagnostic" : "Next question"}<span>→</span></button></div>
              </div> : <CompletedLine title="Diagnostic complete" detail="Results below come directly from your submitted answers." />}
            </section>}

            {stage !== "onboarding" && stage !== "upload" && stage !== "diagnostic" && <section className="journey-step" id="baseline">
              <SectionHeading number="04" eyebrow="Your learner baseline" title="A starting point, not a label." detail="These topic scores are the diagnostic results returned by FriendOS." />
              <div className="score-list">{topicScores.map((score) => <div className="score-row" key={score.topic}><div><strong>{score.topic}</strong><span>{score.correct} correct of {score.total}</span></div><div className="score-meter"><div style={{ width: `${Math.max(0, Math.min(100, score.score * 100))}%` }} /></div><b>{Math.round(score.score * 100)}%</b></div>)}</div>
              {error && stage === "baseline" && <ErrorNote>{error}</ErrorNote>}
              {stage === "baseline" && <button className="button button-dark" onClick={() => void beginLearning()} disabled={busy}>{busy ? "Opening a learning session…" : "Continue to learning"}<span>→</span></button>}
            </section>}

            {stage !== "onboarding" && stage !== "upload" && stage !== "diagnostic" && stage !== "baseline" && <section className="journey-step" id="practice">
              <SectionHeading number="05" eyebrow="The learning session" title="A space for the work." detail={weakestTopic ? `Session topic · ${weakestTopic}` : undefined} />
              {stage === "practice" ? <PracticeSessionPanel sessionId={learningSessionId} busy={busy} error={error} onFinish={() => void finishSession()} /> : <CompletedLine title="Session closed" detail="No practice answers or behavioral events were recorded in this session." />}
            </section>}

            {stage === "review" && <section className="journey-step review-step" id="review">
              <SectionHeading number="06" eyebrow="A next step, shaped by evidence" title="What comes next." detail="The recommendation and history below are returned by the existing FriendOS APIs." />
              {error && <ErrorNote>{error}</ErrorNote>}
              {recommendation && <div className="recommendation"><div className="recommendation-label"><span className="eyebrow">FRIENDOS RECOMMENDS</span><span className="recommendation-type">{recommendation.recommendation_type.replaceAll("_", " ")}</span></div><h3>{recommendation.activity}</h3><p>{recommendation.reason}</p><div className="recommendation-meta"><span>{recommendation.topic}</span><span>{recommendation.difficulty}</span></div>{typeof skillProfile[recommendation.topic] === "number" && <p className="baseline-note">Diagnostic baseline for {recommendation.topic}: {Math.round(skillProfile[recommendation.topic] * 100)}%</p>}{recommendation.evidence.length > 0 && <ul>{recommendation.evidence.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>}</div>}
              {summary && <div className="summary-block"><p className="eyebrow">LEARNING SUMMARY</p>{summary.total_questions === 0 ? <p>No learning-question activity is recorded yet. The practice engine is being prepared.</p> : <div className="summary-stats"><div><b>{summary.total_questions}</b><span>questions encountered</span></div><div><b>{summary.correct_answers} / {summary.incorrect_answers}</b><span>correct / incorrect</span></div><div><b>{summary.correct_answers + summary.incorrect_answers > 0 ? `${Math.round(summary.accuracy * 100)}%` : "—"}</b><span>accuracy of answered questions</span></div><div><b>{summary.hints_requested}</b><span>hints requested</span></div><div><b>{summary.questions_skipped}</b><span>questions skipped</span></div><div><b>{summary.average_time_seconds > 0 ? `${summary.average_time_seconds.toFixed(1)}s` : "—"}</b><span>average response time</span></div></div>}</div>}
              <div className="history-block"><p className="eyebrow">RECENT ADAPTATIONS</p>{history.length === 0 ? <p>No recommendation history yet.</p> : <ol>{history.slice(0, 5).map((entry) => <li key={entry.recommendation_id}><span>{entry.recommendation_type.replaceAll("_", " ")}</span><strong>{entry.topic}</strong><time>{new Date(entry.created_at).toLocaleDateString()}</time></li>)}</ol>}</div>
              <a className="text-button final-link" href="#top">Return to the beginning ↑</a>
            </section>}
          </div>
        </div>
      </section>
      <footer className="site-footer"><a className="wordmark" href="#top">FriendOS<span>®</span></a><p>A companion for the way you learn.</p><span className="eyebrow">PLAN · ACT · OBSERVE · LEARN · ADAPT</span></footer>
    </main>
  );
}

function CompletedLine({ title, detail }: { title: string; detail: string }) {
  return <div className="completed-line"><span aria-hidden="true">✓</span><div><strong>{title}</strong><p>{detail}</p></div></div>;
}
