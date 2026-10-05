// Shared TypeScript types mirroring backend Pydantic schemas exactly.
// DO NOT modify — these must stay in sync with the FastAPI contracts.

export interface LearnerResponse {
  success: boolean;
  learner_id: string;
  message: string;
}

export interface Topic {
  name: string;
  description: string;
  difficulty: "beginner" | "intermediate" | "advanced";
}

export interface DiagnosticQuestion {
  question: string;
  options: [string, string, string, string];
  correct_answer: number;
  topic: string;
  difficulty: string;
}

export interface ClientQuestion {
  question_id: string;
  question: string;
  options: [string, string, string, string];
  topic: string;
  difficulty: string;
}

export interface MaterialUploadResponse {
  success: boolean;
  material_id: string;
  title: string;
  topics: Topic[];
  diagnostic_questions: DiagnosticQuestion[];
}

export interface StartDiagnosticResponse {
  success: boolean;
  session_id: string;
  questions: ClientQuestion[];
}

export interface LearnerAnswer {
  question_id: string;
  selected_answer: number | null;
}

export interface TopicScore {
  topic: string;
  correct: number;
  total: number;
  score: number;
}

export interface SubmitDiagnosticResponse {
  success: boolean;
  session_id: string;
  overall_score: number;
  topic_scores: TopicScore[];
  skill_profile: Record<string, number>;
}

export interface LearningSessionResponse {
  success: boolean;
  session_id: string;
}

export interface RecordEventRequest {
  session_id: string;
  question_id: string;
  event_type: "answer" | "hint" | "skip" | "start" | "complete";
  is_correct?: boolean;
  attempt_number: number;
  time_taken_seconds?: number;
  hint_requested: boolean;
  skipped: boolean;
}

export interface CompleteSessionResponse {
  success: boolean;
  session_id: string;
  events_recorded: number;
  questions_answered: number;
  questions_skipped: number;
}

export interface TopicSummary {
  attempts: number;
  accuracy: number;
  average_time_seconds: number;
  hints_requested: number;
  skipped: number;
}

export interface LearnerBehaviorSummary {
  learner_id: string;
  total_questions: number;
  correct_answers: number;
  incorrect_answers: number;
  accuracy: number;
  average_time_seconds: number;
  hints_requested: number;
  questions_skipped: number;
  topic_summary: Record<string, TopicSummary>;
}

export type RecommendationType =
  | "REVIEW_CONCEPT"
  | "PRACTICE_EASY"
  | "PRACTICE_STANDARD"
  | "PRACTICE_HARD"
  | "MOVE_TO_NEXT_TOPIC"
  | "REVIEW_WITH_HINT";

export interface AdaptiveRecommendation {
  recommendation_type: RecommendationType;
  topic: string;
  difficulty: "beginner" | "intermediate" | "advanced";
  reason: string;
  activity: string;
  evidence: string[];
}

export interface RecommendResponse {
  success: boolean;
  recommendation: AdaptiveRecommendation;
}

export interface HistoryEntry {
  recommendation_id: string;
  learner_id: string;
  material_id: string;
  recommendation_type: RecommendationType;
  topic: string;
  difficulty: string;
  reason: string;
  activity: string;
  evidence: string[];
  created_at: string;
}

export interface HistoryResponse {
  learner_id: string;
  history: HistoryEntry[];
}

// App-level state shape
export interface AppState {
  learnerId: string | null;
  learnerName: string | null;
  materialId: string | null;
  topics: Topic[];
  diagnosticSessionId: string | null;
  skillProfile: Record<string, number>;
  learningSessionId: string | null;
  currentRecommendation: AdaptiveRecommendation | null;
}
