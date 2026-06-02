// ─── Core API types ───────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  last_login: string | null;
  preferences: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// ─── Reddit types ─────────────────────────────────────────────────────────────

export type AnalysisStatus = "pending" | "in_progress" | "completed" | "failed";
export type SentimentLabel = "very_positive" | "positive" | "neutral" | "negative" | "very_negative" | "mixed";

export interface SubredditAnalysis {
  id: string;
  user_id: string;
  subreddit_name: string;
  status: AnalysisStatus;
  subscriber_count: number | null;
  active_users: number | null;
  description: string | null;
  time_period: string;
  posts_analyzed: number;
  overall_sentiment: SentimentLabel | null;
  sentiment_scores: Record<string, number> | null;
  top_topics: Record<string, number> | null;
  trending_keywords: Record<string, number> | null;
  avg_score: number | null;
  avg_comments: number | null;
  engagement_rate: number | null;
  ai_summary: string | null;
  key_insights: Record<string, string> | null;
  opportunities: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Research types ───────────────────────────────────────────────────────────

export type ResearchStatus = "pending" | "in_progress" | "completed" | "failed" | "cancelled";
export type ResearchType = "web_search" | "reddit_analysis" | "multi_source" | "deep_dive" | "competitive";

export interface ResearchSession {
  id: string;
  user_id: string;
  title: string;
  query: string;
  research_type: ResearchType;
  status: ResearchStatus;
  summary: string | null;
  sources_count: number;
  metadata: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Security types ───────────────────────────────────────────────────────────

export type InvestigationStatus = "pending" | "in_progress" | "completed" | "failed";
export type InvestigationType = "account_scan" | "identity_search" | "threat_assessment" | "osint_collection" | "background_check";
export type SeverityLevel = "critical" | "high" | "medium" | "low" | "info";

export interface SecurityInvestigation {
  id: string;
  user_id: string;
  title: string;
  target: string;
  investigation_type: InvestigationType;
  status: InvestigationStatus;
  findings_count: number;
  risk_score: number | null;
  risk_level: SeverityLevel | null;
  executive_summary: string | null;
  recommendations: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Memory types ─────────────────────────────────────────────────────────────

export type MemoryType = "conversation" | "research" | "subreddit_report" | "competitor_report" | "growth_experiment" | "decision" | "preference" | "insight" | "fact" | "note";

export interface Memory {
  id: string;
  user_id: string;
  collection_id: string | null;
  title: string;
  content: string;
  summary: string | null;
  memory_type: MemoryType;
  tags: string[] | null;
  importance_score: number;
  access_count: number;
  is_pinned: boolean;
  is_archived: boolean;
  source_type: string | null;
  source_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryCollection {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  color: string | null;
  icon: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

// ─── Report types ─────────────────────────────────────────────────────────────

export type ReportType = "subreddit_analysis" | "topic_discovery" | "security_investigation" | "research_session" | "competitor_analysis" | "growth_strategy" | "custom";
export type ReportFormat = "pdf" | "markdown" | "html" | "json";
export type ReportStatus = "generating" | "completed" | "failed";

export interface Report {
  id: string;
  user_id: string;
  title: string;
  report_type: ReportType;
  status: ReportStatus;
  format: ReportFormat;
  executive_summary: string | null;
  file_path: string | null;
  file_size_bytes: number | null;
  source_id: string | null;
  is_public: boolean;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Agent types ──────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  agent_used?: string;
}

export interface ChatResponse {
  message: string;
  conversation_id: string;
  agent_used: string;
  tools_called: string[];
  memory_retrieved: number;
  processing_time_ms: number;
}

// ─── API response wrappers ────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface DashboardStats {
  research_sessions: number;
  subreddit_analyses: number;
  security_investigations: number;
  memories: number;
  reports: number;
}
