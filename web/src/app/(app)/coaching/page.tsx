"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Target,
  Plus,
  Users,
  FileText,
  AlertTriangle,
  Lightbulb,
  HelpCircle,
  Calendar,
  BookOpen,
  X,
  Send,
} from "lucide-react";

interface Client {
  client_id: string;
  name: string;
  coach_chat_id: string;
  coach_channel: string;
  timezone: string;
  created_at?: string;
}

interface PrepSummary {
  client_name: string;
  last_session: string | null;
  ideas: string;
  questions: string;
  flags: string;
  flag_count: number;
  history: string;
}

const COACHING_API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  const match = document.cookie.match(/auth_token=([^;]+)/);
  return match ? match[1] : null;
}

async function fetchCoaching<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const res = await fetch(`${COACHING_API}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }
  return res.json();
}

type TabType = "prep" | "ideas" | "questions" | "sessions" | "history" | "flags";

export default function CoachingPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [prepSummary, setPrepSummary] = useState<PrepSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newClient, setNewClient] = useState({ name: "", client_id: "" });
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("prep");

  // Input states
  const [newIdea, setNewIdea] = useState({ content: "", realm: "assess" });
  const [newQuestion, setNewQuestion] = useState("");
  const [newSession, setNewSession] = useState({ date: new Date().toISOString().split("T")[0], content: "" });
  const [newFlag, setNewFlag] = useState({ message: "", grounding_offered: false, coach_notified: false });
  const [editHistory, setEditHistory] = useState("");
  const [isEditing, setIsEditing] = useState(false);

  // Session list
  const [sessions, setSessions] = useState<string[]>([]);
  const [selectedSessionDate, setSelectedSessionDate] = useState<string | null>(null);
  const [sessionContent, setSessionContent] = useState<string>("");

  useEffect(() => {
    loadClients();
  }, []);

  const loadClients = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await fetchCoaching<{ clients: Client[] }>("/coaching/clients");
      setClients(data.clients);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load clients");
    } finally {
      setIsLoading(false);
    }
  };

  const loadPrepSummary = async (clientId: string) => {
    try {
      const data = await fetchCoaching<PrepSummary>(`/coaching/clients/${encodeURIComponent(clientId)}/prep`);
      setPrepSummary(data);
      setEditHistory(data.history);
    } catch (err) {
      console.error("Failed to load prep summary:", err);
    }
  };

  const loadSessions = async (clientId: string) => {
    try {
      const data = await fetchCoaching<{ sessions: string[] }>(`/coaching/clients/${encodeURIComponent(clientId)}/sessions`);
      setSessions(data.sessions);
    } catch (err) {
      console.error("Failed to load sessions:", err);
    }
  };

  const loadSessionContent = async (clientId: string, date: string) => {
    try {
      const data = await fetchCoaching<{ content: string }>(`/coaching/clients/${encodeURIComponent(clientId)}/sessions/${date}`);
      setSessionContent(data.content);
      setSelectedSessionDate(date);
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  };

  const selectClient = (client: Client) => {
    setSelectedClient(client);
    setActiveTab("prep");
    loadPrepSummary(client.client_id);
    loadSessions(client.client_id);
  };

  const handleAddClient = async () => {
    if (!newClient.name.trim() || !newClient.client_id.trim()) return;
    try {
      const client = await fetchCoaching<Client>("/coaching/clients", {
        method: "POST",
        body: JSON.stringify({
          name: newClient.name,
          client_id: newClient.client_id,
          coach_chat_id: "web",
          coach_channel: "web",
        }),
      });
      setClients([...clients, client]);
      setNewClient({ name: "", client_id: "" });
      setShowAddForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add client");
    }
  };

  const handleAddIdea = async () => {
    if (!selectedClient || !newIdea.content.trim()) return;
    try {
      await fetchCoaching(`/coaching/clients/${encodeURIComponent(selectedClient.client_id)}/ideas`, {
        method: "POST",
        body: JSON.stringify(newIdea),
      });
      setNewIdea({ content: "", realm: "assess" });
      await loadPrepSummary(selectedClient.client_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add idea");
    }
  };

  const handleAddQuestion = async () => {
    if (!selectedClient || !newQuestion.trim()) return;
    try {
      await fetchCoaching(`/coaching/clients/${encodeURIComponent(selectedClient.client_id)}/questions`, {
        method: "POST",
        body: JSON.stringify({ content: newQuestion }),
      });
      setNewQuestion("");
      await loadPrepSummary(selectedClient.client_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add question");
    }
  };

  const handleAddSession = async () => {
    if (!selectedClient || !newSession.date || !newSession.content.trim()) return;
    try {
      await fetchCoaching(`/coaching/clients/${encodeURIComponent(selectedClient.client_id)}/sessions`, {
        method: "POST",
        body: JSON.stringify(newSession),
      });
      setNewSession({ date: new Date().toISOString().split("T")[0], content: "" });
      await loadSessions(selectedClient.client_id);
      await loadPrepSummary(selectedClient.client_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add session");
    }
  };

  const handleAddFlag = async () => {
    if (!selectedClient || !newFlag.message.trim()) return;
    try {
      await fetchCoaching(`/coaching/clients/${encodeURIComponent(selectedClient.client_id)}/flags`, {
        method: "POST",
        body: JSON.stringify(newFlag),
      });
      setNewFlag({ message: "", grounding_offered: false, coach_notified: false });
      await loadPrepSummary(selectedClient.client_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add flag");
    }
  };

  const handleSaveHistory = async () => {
    if (!selectedClient) return;
    try {
      await fetchCoaching(`/coaching/clients/${encodeURIComponent(selectedClient.client_id)}/history`, {
        method: "PUT",
        body: JSON.stringify({ content: editHistory }),
      });
      setIsEditing(false);
      await loadPrepSummary(selectedClient.client_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save history");
    }
  };

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: "prep", label: "Prep", icon: <FileText className="h-4 w-4" /> },
    { id: "ideas", label: "Ideas", icon: <Lightbulb className="h-4 w-4" /> },
    { id: "questions", label: "Questions", icon: <HelpCircle className="h-4 w-4" /> },
    { id: "sessions", label: "Sessions", icon: <Calendar className="h-4 w-4" /> },
    { id: "history", label: "Arc", icon: <BookOpen className="h-4 w-4" /> },
    { id: "flags", label: "Flags", icon: <AlertTriangle className="h-4 w-4" /> },
  ];

  return (
    <div className="flex-1 flex flex-col">
      <Header title="Coaching" />

      <div className="flex-1 flex overflow-hidden">
        {/* Client List */}
        <div className="w-64 border-r border-border p-4 overflow-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold flex items-center gap-2">
              <Users className="h-4 w-4" />
              Clients
            </h2>
            <Button size="icon" variant="ghost" onClick={() => setShowAddForm(!showAddForm)}>
              {showAddForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            </Button>
          </div>

          {showAddForm && (
            <div className="mb-4 p-3 bg-muted rounded-lg space-y-2">
              <Input
                placeholder="Client name"
                value={newClient.name}
                onChange={(e) => setNewClient({ ...newClient, name: e.target.value })}
              />
              <Input
                placeholder="Client ID (e.g., telegram:123)"
                value={newClient.client_id}
                onChange={(e) => setNewClient({ ...newClient, client_id: e.target.value })}
              />
              <Button size="sm" onClick={handleAddClient} className="w-full">
                Add Client
              </Button>
            </div>
          )}

          {error && <p className="text-sm text-red-500 mb-4">{error}</p>}

          {isLoading ? (
            <p className="text-muted-foreground text-sm">Loading...</p>
          ) : clients.length === 0 ? (
            <div className="text-center py-8">
              <Target className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">No clients yet</p>
            </div>
          ) : (
            <div className="space-y-1">
              {clients.map((client) => (
                <button
                  key={client.client_id}
                  onClick={() => selectClient(client)}
                  className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                    selectedClient?.client_id === client.client_id
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-muted"
                  }`}
                >
                  <p className="font-medium truncate">{client.name}</p>
                  <p className="text-xs opacity-70 truncate">{client.client_id}</p>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Client Details */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {selectedClient && prepSummary ? (
            <>
              {/* Tabs */}
              <div className="flex gap-1 p-2 border-b border-border bg-muted/30">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                      activeTab === tab.id
                        ? "bg-background shadow-sm font-medium"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {tab.icon}
                    {tab.label}
                    {tab.id === "flags" && prepSummary.flag_count > 0 && (
                      <span className="ml-1 px-1.5 py-0.5 text-xs bg-red-500 text-white rounded-full">
                        {prepSummary.flag_count}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="flex-1 p-6 overflow-auto">
                <h1 className="text-2xl font-bold mb-6">{prepSummary.client_name}</h1>

                {/* Prep Tab */}
                {activeTab === "prep" && (
                  <div className="grid gap-6 max-w-3xl">
                    {prepSummary.flag_count > 0 && (
                      <div className="p-4 rounded-lg border-2 border-red-500 bg-red-500/10">
                        <h2 className="font-semibold flex items-center gap-2 text-red-500 mb-2">
                          <AlertTriangle className="h-5 w-5" />
                          Flags ({prepSummary.flag_count})
                        </h2>
                        <pre className="whitespace-pre-wrap text-sm">{prepSummary.flags}</pre>
                      </div>
                    )}

                    <div className="p-4 rounded-lg bg-muted">
                      <h2 className="font-semibold mb-2">Last Session</h2>
                      <p className="text-muted-foreground">
                        {prepSummary.last_session || "No sessions recorded"}
                      </p>
                    </div>

                    <div className="p-4 rounded-lg bg-muted">
                      <h2 className="font-semibold flex items-center gap-2 mb-2">
                        <HelpCircle className="h-4 w-4" />
                        Questions
                      </h2>
                      {prepSummary.questions.trim() ? (
                        <pre className="whitespace-pre-wrap text-sm">{prepSummary.questions}</pre>
                      ) : (
                        <p className="text-sm text-muted-foreground">No questions recorded</p>
                      )}
                    </div>

                    <div className="p-4 rounded-lg bg-muted">
                      <h2 className="font-semibold flex items-center gap-2 mb-2">
                        <Lightbulb className="h-4 w-4" />
                        Ideas
                      </h2>
                      {prepSummary.ideas.trim() ? (
                        <pre className="whitespace-pre-wrap text-sm">{prepSummary.ideas}</pre>
                      ) : (
                        <p className="text-sm text-muted-foreground">No ideas recorded</p>
                      )}
                    </div>

                    {prepSummary.history.trim() && (
                      <div className="p-4 rounded-lg bg-muted">
                        <h2 className="font-semibold mb-2">Coaching Arc</h2>
                        <pre className="whitespace-pre-wrap text-sm">{prepSummary.history}</pre>
                      </div>
                    )}
                  </div>
                )}

                {/* Ideas Tab */}
                {activeTab === "ideas" && (
                  <div className="max-w-3xl">
                    <div className="mb-6 p-4 rounded-lg border border-border bg-muted/50">
                      <h3 className="font-medium mb-3">Add Idea</h3>
                      <textarea
                        placeholder="What's the idea?"
                        value={newIdea.content}
                        onChange={(e) => setNewIdea({ ...newIdea, content: e.target.value })}
                        className="w-full p-3 rounded-md border border-input bg-background text-sm min-h-[100px] mb-3"
                      />
                      <div className="flex gap-2 items-center">
                        <select
                          value={newIdea.realm}
                          onChange={(e) => setNewIdea({ ...newIdea, realm: e.target.value })}
                          className="px-3 py-2 rounded-md border border-input bg-background text-sm"
                        >
                          <option value="assess">Assess</option>
                          <option value="decide">Decide</option>
                          <option value="do">Do</option>
                        </select>
                        <Button onClick={handleAddIdea} disabled={!newIdea.content.trim()}>
                          <Send className="h-4 w-4 mr-2" />
                          Add Idea
                        </Button>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg bg-muted">
                      <h3 className="font-semibold mb-3">Captured Ideas</h3>
                      {prepSummary.ideas.trim() ? (
                        <pre className="whitespace-pre-wrap text-sm">{prepSummary.ideas}</pre>
                      ) : (
                        <p className="text-sm text-muted-foreground">No ideas recorded yet</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Questions Tab */}
                {activeTab === "questions" && (
                  <div className="max-w-3xl">
                    <div className="mb-6 p-4 rounded-lg border border-border bg-muted/50">
                      <h3 className="font-medium mb-3">Add Question</h3>
                      <div className="flex gap-2">
                        <Input
                          placeholder="Question to explore in next session..."
                          value={newQuestion}
                          onChange={(e) => setNewQuestion(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleAddQuestion()}
                        />
                        <Button onClick={handleAddQuestion} disabled={!newQuestion.trim()}>
                          <Send className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg bg-muted">
                      <h3 className="font-semibold mb-3">Questions for Next Session</h3>
                      {prepSummary.questions.trim() ? (
                        <pre className="whitespace-pre-wrap text-sm">{prepSummary.questions}</pre>
                      ) : (
                        <p className="text-sm text-muted-foreground">No questions recorded yet</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Sessions Tab */}
                {activeTab === "sessions" && (
                  <div className="max-w-3xl">
                    <div className="mb-6 p-4 rounded-lg border border-border bg-muted/50">
                      <h3 className="font-medium mb-3">Add Session Notes</h3>
                      <div className="space-y-3">
                        <Input
                          type="date"
                          value={newSession.date}
                          onChange={(e) => setNewSession({ ...newSession, date: e.target.value })}
                        />
                        <textarea
                          placeholder="Session notes..."
                          value={newSession.content}
                          onChange={(e) => setNewSession({ ...newSession, content: e.target.value })}
                          className="w-full p-3 rounded-md border border-input bg-background text-sm min-h-[150px]"
                        />
                        <Button onClick={handleAddSession} disabled={!newSession.content.trim()}>
                          <Plus className="h-4 w-4 mr-2" />
                          Save Session
                        </Button>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg bg-muted">
                      <h3 className="font-semibold mb-3">Past Sessions</h3>
                      {sessions.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No sessions recorded yet</p>
                      ) : (
                        <div className="space-y-2">
                          {sessions.map((date) => (
                            <button
                              key={date}
                              onClick={() => loadSessionContent(selectedClient.client_id, date)}
                              className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
                                selectedSessionDate === date
                                  ? "bg-primary text-primary-foreground"
                                  : "bg-background hover:bg-muted"
                              }`}
                            >
                              {date}
                            </button>
                          ))}
                        </div>
                      )}

                      {selectedSessionDate && sessionContent && (
                        <div className="mt-4 p-4 rounded-lg bg-background border border-border">
                          <h4 className="font-medium mb-2">Session: {selectedSessionDate}</h4>
                          <pre className="whitespace-pre-wrap text-sm">{sessionContent}</pre>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* History/Arc Tab */}
                {activeTab === "history" && (
                  <div className="max-w-3xl">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold">Coaching Arc</h3>
                      {!isEditing ? (
                        <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
                          Edit
                        </Button>
                      ) : (
                        <div className="flex gap-2">
                          <Button size="sm" onClick={handleSaveHistory}>Save</Button>
                          <Button variant="ghost" size="sm" onClick={() => {
                            setIsEditing(false);
                            setEditHistory(prepSummary.history);
                          }}>
                            Cancel
                          </Button>
                        </div>
                      )}
                    </div>

                    {isEditing ? (
                      <textarea
                        value={editHistory}
                        onChange={(e) => setEditHistory(e.target.value)}
                        className="w-full p-4 rounded-lg border border-input bg-background text-sm min-h-[400px] font-mono"
                        placeholder="# Coaching Arc&#10;&#10;Document the client's journey, goals, breakthroughs, and patterns..."
                      />
                    ) : (
                      <div className="p-4 rounded-lg bg-muted">
                        {prepSummary.history.trim() ? (
                          <pre className="whitespace-pre-wrap text-sm">{prepSummary.history}</pre>
                        ) : (
                          <p className="text-sm text-muted-foreground">
                            No coaching arc documented yet. Click Edit to start documenting the client&apos;s journey.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Flags Tab */}
                {activeTab === "flags" && (
                  <div className="max-w-3xl">
                    <div className="mb-6 p-4 rounded-lg border-2 border-red-500/50 bg-red-500/5">
                      <h3 className="font-medium mb-3 text-red-500 flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4" />
                        Add Emergency Flag
                      </h3>
                      <textarea
                        placeholder="Describe the concerning message or behavior..."
                        value={newFlag.message}
                        onChange={(e) => setNewFlag({ ...newFlag, message: e.target.value })}
                        className="w-full p-3 rounded-md border border-input bg-background text-sm min-h-[100px] mb-3"
                      />
                      <div className="flex flex-wrap gap-4 mb-3">
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={newFlag.grounding_offered}
                            onChange={(e) => setNewFlag({ ...newFlag, grounding_offered: e.target.checked })}
                            className="rounded"
                          />
                          Grounding offered
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={newFlag.coach_notified}
                            onChange={(e) => setNewFlag({ ...newFlag, coach_notified: e.target.checked })}
                            className="rounded"
                          />
                          Coach notified
                        </label>
                      </div>
                      <Button
                        onClick={handleAddFlag}
                        disabled={!newFlag.message.trim()}
                        variant="destructive"
                      >
                        <AlertTriangle className="h-4 w-4 mr-2" />
                        Add Flag
                      </Button>
                    </div>

                    <div className="p-4 rounded-lg bg-muted">
                      <h3 className="font-semibold mb-3">Flag History</h3>
                      {prepSummary.flags.trim() ? (
                        <pre className="whitespace-pre-wrap text-sm">{prepSummary.flags}</pre>
                      ) : (
                        <p className="text-sm text-muted-foreground">No flags recorded</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="h-full flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <Target className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Select a client to view their coaching data</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
