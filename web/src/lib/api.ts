// Direct API URL for auth endpoints (bypasses proxy to ensure headers are forwarded)
const DIRECT_API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// For non-auth endpoints, use proxy (empty string) to avoid CORS issues
const PROXY_API_URL = typeof window !== "undefined" ? "" : DIRECT_API_URL;

interface ApiOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  direct?: boolean; // Use direct API URL (bypass proxy)
  token?: string; // Explicit token (overrides cookie)
}

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  const match = document.cookie.match(/auth_token=([^;]+)/);
  return match ? match[1] : null;
}

async function api<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {}, direct = false, token: explicitToken } = options;

  // Use explicit token if provided, otherwise try to get from cookie
  const token = explicitToken || getAuthToken();
  const authHeaders: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};

  // Use direct URL for auth endpoints or when explicitly requested
  const baseUrl = direct ? DIRECT_API_URL : PROXY_API_URL;

  const config: RequestInit = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...headers,
    },
    credentials: "include",
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${baseUrl}${endpoint}`, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }

  return response.json();
}

// Auth - use direct API calls to ensure auth headers are forwarded
export const authApi = {
  getLoginUrl: () => api<{ redirect_url: string }>("/auth/login", { direct: true }),
  logout: () => api("/auth/logout", { method: "POST", direct: true }),
  getMe: (token?: string) => api<User>("/auth/me", { direct: true, token }),
  updateTheme: (theme: string) =>
    api("/auth/me/theme", { method: "PATCH", body: { theme }, direct: true }),
};

// Chat - use direct API calls to avoid collision with app routes
export const chatApi = {
  sendMessage: (message: string, sessionId?: string) =>
    api<ChatResponse>("/chat/message", {
      method: "POST",
      body: { message, session_id: sessionId },
      direct: true,
    }),
  getRealm: () => api<RealmFlow>("/chat/realm", { direct: true }),
};

// Sessions - use direct API calls
export const sessionsApi = {
  list: () => api<{ sessions: Session[] }>("/sessions", { direct: true }),
  create: (name: string, context?: string, projectId?: string) =>
    api<Session>("/sessions", {
      method: "POST",
      body: { name, context, project_id: projectId },
      direct: true,
    }),
  get: (id: string) => api<Session>(`/sessions/${id}`, { direct: true }),
  delete: (id: string) => api(`/sessions/${id}`, { method: "DELETE", direct: true }),
};

// Projects - use direct API calls to avoid collision with app routes
export const projectsApi = {
  list: (realm?: string) =>
    api<{ projects: Project[] }>(`/projects${realm ? `?realm=${realm}` : ""}`, { direct: true }),
  get: (id: string) => api<ProjectDetail>(`/projects/${id}`, { direct: true }),
  getTasks: (id: string) => api<{ tasks: Task[] }>(`/projects/${id}/tasks`, { direct: true }),
  create: (name: string, realm: string = "assess", repo?: string) =>
    api<Project>("/projects", {
      method: "POST",
      body: { name, realm, repo },
      direct: true,
    }),
  moveRealm: (id: string, targetRealm: string, reason?: string) =>
    api(`/projects/${id}/move`, {
      method: "POST",
      body: { target_realm: targetRealm, reason },
      direct: true,
    }),
};

// Memory - use direct API calls to avoid collision with app routes
export const memoryApi = {
  getToday: () => api<TodayMemory>("/memory/today", { direct: true }),
  getRecent: (days?: number) =>
    api<MemoryEntry[]>(`/memory/recent${days ? `?days=${days}` : ""}`, { direct: true }),
  getLongTerm: () => api<{ content: string }>("/memory/long-term", { direct: true }),
  search: (query: string, collection?: string, limit?: number) =>
    api<SearchResponse>(
      `/memory/search?q=${encodeURIComponent(query)}${
        collection ? `&collection=${collection}` : ""
      }${limit ? `&limit=${limit}` : ""}`,
      { direct: true }
    ),
};

// Notifications - use direct API calls
export const notificationsApi = {
  list: (limit?: number, unreadOnly?: boolean) =>
    api<NotificationList>(
      `/notifications?limit=${limit || 50}${unreadOnly ? "&unread_only=true" : ""}`,
      { direct: true }
    ),
  markRead: (id: string) =>
    api(`/notifications/${id}/read`, { method: "POST", direct: true }),
  markAllRead: () => api("/notifications/read-all", { method: "POST", direct: true }),
  getUnreadCount: () => api<{ unread_count: number }>("/notifications/count", { direct: true }),
};

// System - use direct for public endpoints that don't need auth
export const systemApi = {
  health: () => api<{ status: string; version: string }>("/system/health", { direct: true }),
  status: () => api<SystemStatus>("/system/status", { direct: true }),
  config: () => api<SystemConfig>("/system/config", { direct: true }),
};

// Types
export interface User {
  id: string;
  email: string;
  name?: string;
  picture_url?: string;
  theme: string;
}

export interface ChatResponse {
  content: string;
  realm?: string;
  timestamp: string;
}

export interface RealmFlow {
  current_realm?: string;
  today: {
    assess: number;
    decide: number;
    do: number;
  };
  history: Array<{
    time: string;
    realm: string;
  }>;
}

export interface Session {
  id: string;
  name: string;
  context?: string;
  project_id?: string;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  name: string;
  realm: string;
  repo?: string;
  current_version?: string;
}

export interface ProjectDetail extends Project {
  realm_time: string;
  tasks: Task[];
}

export interface Task {
  id: string;
  title: string;
  description?: string;
  type: string;
  status: string;
  version?: string;
  branch?: string;
}

export interface TodayMemory {
  date: string;
  content: string;
  has_content: boolean;
}

export interface MemoryEntry {
  date: string;
  content: string;
}

export interface SearchResult {
  text: string;
  score: number;
  source?: string;
  title?: string;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  body?: string;
  urgency: string;
  action_url?: string;
  created_at: string;
  read_at?: string;
}

export interface NotificationList {
  notifications: Notification[];
  unread_count: number;
}

export interface SystemStatus {
  version: string;
  uptime?: string;
  websocket_connections: number;
  connected_users: number;
}

export interface SystemConfig {
  oauth_provider: string;
  features: {
    coaching: boolean;
    projects: boolean;
    vector_memory: boolean;
  };
}
