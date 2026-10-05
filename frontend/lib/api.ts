import axios from "axios";
import type {
  LearnerResponse,
  MaterialUploadResponse,
  StartDiagnosticResponse,
  LearnerAnswer,
  SubmitDiagnosticResponse,
  LearningSessionResponse,
  RecordEventRequest,
  CompleteSessionResponse,
  LearnerBehaviorSummary,
  RecommendResponse,
  HistoryResponse,
  PracticeQuestion,
  PracticeAnswerRequest,
  PracticeAnswerResponse,
} from "./types";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  timeout: 180_000, // Gemma can be slow
});

// ── Onboarding ────────────────────────────────────────────────────────

export async function onboardLearner(payload: {
  name: string;
  learning_goal: string;
  known_topics: string[];
  weak_topics: string[];
}): Promise<LearnerResponse> {
  const { data } = await api.post<LearnerResponse>("/api/onboard", payload);
  return data;
}

// ── Material ──────────────────────────────────────────────────────────

export async function uploadMaterial(file: File): Promise<MaterialUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<MaterialUploadResponse>(
    "/api/material/upload",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

// ── Diagnostic ────────────────────────────────────────────────────────

export async function startDiagnostic(payload: {
  learner_id: string;
  material_id: string;
}): Promise<StartDiagnosticResponse> {
  const { data } = await api.post<StartDiagnosticResponse>(
    "/api/diagnostic/start",
    payload
  );
  return data;
}

export async function submitDiagnostic(
  sessionId: string,
  answers: LearnerAnswer[]
): Promise<SubmitDiagnosticResponse> {
  const { data } = await api.post<SubmitDiagnosticResponse>(
    `/api/diagnostic/${sessionId}/submit`,
    { answers }
  );
  return data;
}

// ── Learning Sessions ─────────────────────────────────────────────────

export async function startLearningSession(payload: {
  learner_id: string;
  material_id: string;
  topic: string;
}): Promise<LearningSessionResponse> {
  const { data } = await api.post<LearningSessionResponse>(
    "/api/learning/session/start",
    payload
  );
  return data;
}

export async function recordEvent(
  payload: RecordEventRequest
): Promise<void> {
  await api.post("/api/learning/event", payload);
}

export async function completeLearningSession(
  sessionId: string
): Promise<CompleteSessionResponse> {
  const { data } = await api.post<CompleteSessionResponse>(
    `/api/learning/session/${sessionId}/complete`
  );
  return data;
}

export async function getLearnerSummary(
  learnerId: string
): Promise<LearnerBehaviorSummary> {
  const { data } = await api.get<LearnerBehaviorSummary>(
    `/api/learning/summary/${learnerId}`
  );
  return data;
}

// ── Adaptive ──────────────────────────────────────────────────────────

export async function getRecommendation(payload: {
  learner_id: string;
  material_id: string;
}): Promise<RecommendResponse> {
  const { data } = await api.post<RecommendResponse>(
    "/api/adaptive/recommend",
    payload
  );
  return data;
}

export async function getHistory(learnerId: string): Promise<HistoryResponse> {
  const { data } = await api.get<HistoryResponse>(
    `/api/adaptive/history/${learnerId}`
  );
  return data;
}

// ── Practice Flow ─────────────────────────────────────────────────────

export async function getPracticeQuestion(
  sessionId: string
): Promise<PracticeQuestion> {
  const { data } = await api.get<PracticeQuestion>(
    `/api/learning/session/${sessionId}/question`
  );
  return data;
}

export async function submitPracticeAnswer(
  sessionId: string,
  payload: PracticeAnswerRequest
): Promise<PracticeAnswerResponse> {
  const { data } = await api.post<PracticeAnswerResponse>(
    `/api/learning/session/${sessionId}/answer`,
    payload
  );
  return data;
}
