"use client";

import { useEffect, useState } from "react";
import { projectsApi, Project, ProjectDetail, Task } from "@/lib/api";
import { Header } from "@/components/layout/header";
import { RealmBadge } from "@/components/realm/realm-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  FolderKanban,
  Plus,
  X,
  ArrowLeft,
  CheckCircle,
  Circle,
  PlayCircle,
  Calendar,
  AlertCircle,
  Trash2,
  ArrowRight,
} from "lucide-react";

// Direct API for projects
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  const match = document.cookie.match(/auth_token=([^;]+)/);
  return match ? match[1] : null;
}

async function projectApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const res = await fetch(`${API_URL}${endpoint}`, {
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

const statusIcons: Record<string, React.ReactNode> = {
  draft: <Circle className="h-4 w-4 text-muted-foreground" />,
  ready: <CheckCircle className="h-4 w-4 text-blue-500" />,
  unscheduled: <Circle className="h-4 w-4 text-orange-500" />,
  scheduled: <Calendar className="h-4 w-4 text-purple-500" />,
  in_progress: <PlayCircle className="h-4 w-4 text-green-500" />,
  blocked: <AlertCircle className="h-4 w-4 text-red-500" />,
  done: <CheckCircle className="h-4 w-4 text-green-500" />,
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<string | null>(null);
  const [showAddProject, setShowAddProject] = useState(false);
  const [showAddTask, setShowAddTask] = useState(false);
  const [newProject, setNewProject] = useState({ name: "", realm: "assess", repo: "" });
  const [newTask, setNewTask] = useState({ title: "", description: "", type: "feature" });
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scheduleVersion, setScheduleVersion] = useState<{ taskId: string; version: string } | null>(null);

  useEffect(() => {
    loadProjects();
  }, [filter]);

  const loadProjects = async () => {
    try {
      setIsLoading(true);
      const data = await projectsApi.list(filter || undefined);
      setProjects(data.projects);
    } catch (error) {
      console.error("Failed to load projects:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadProjectDetails = async (projectId: string) => {
    try {
      const data = await projectsApi.get(projectId);
      setSelectedProject(data);
    } catch (error) {
      console.error("Failed to load project:", error);
    }
  };

  const handleCreateProject = async () => {
    if (!newProject.name.trim()) return;
    try {
      setIsCreating(true);
      setError(null);
      const project = await projectsApi.create(
        newProject.name,
        newProject.realm,
        newProject.repo || undefined
      );
      setProjects([...projects, project]);
      setNewProject({ name: "", realm: "assess", repo: "" });
      setShowAddProject(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setIsCreating(false);
    }
  };

  const handleCreateTask = async () => {
    if (!selectedProject || !newTask.title.trim()) return;
    try {
      setIsCreating(true);
      setError(null);
      await projectApi(`/projects/${selectedProject.id}/tasks`, {
        method: "POST",
        body: JSON.stringify(newTask),
      });
      await loadProjectDetails(selectedProject.id);
      setNewTask({ title: "", description: "", type: "feature" });
      setShowAddTask(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create task");
    } finally {
      setIsCreating(false);
    }
  };

  const handleTaskAction = async (taskId: string, action: string, body?: object) => {
    if (!selectedProject) return;
    try {
      setError(null);
      await projectApi(`/projects/${selectedProject.id}/tasks/${taskId}/${action}`, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      });
      await loadProjectDetails(selectedProject.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} task`);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    if (!selectedProject) return;
    if (!confirm("Delete this task?")) return;
    try {
      await projectApi(`/projects/${selectedProject.id}/tasks/${taskId}`, {
        method: "DELETE",
      });
      await loadProjectDetails(selectedProject.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete task");
    }
  };

  const handleMoveRealm = async (targetRealm: string) => {
    if (!selectedProject) return;
    try {
      setError(null);
      await projectsApi.moveRealm(selectedProject.id, targetRealm);
      await loadProjectDetails(selectedProject.id);
      await loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to move project");
    }
  };

  const handleScheduleTask = async () => {
    if (!scheduleVersion) return;
    await handleTaskAction(scheduleVersion.taskId, "schedule", { version: scheduleVersion.version });
    setScheduleVersion(null);
  };

  const getNextRealm = (current: string) => {
    if (current === "assess") return "decide";
    if (current === "decide") return "do";
    return null;
  };

  const renderTaskActions = (task: Task) => {
    const realm = selectedProject?.realm;

    if (realm === "assess") {
      if (task.status === "draft") {
        return (
          <div className="flex gap-1">
            <Button size="sm" variant="outline" onClick={() => handleTaskAction(task.id, "ready")}>
              Mark Ready
            </Button>
            <Button size="sm" variant="ghost" onClick={() => handleDeleteTask(task.id)}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        );
      }
    }

    if (realm === "decide") {
      if (task.status === "unscheduled") {
        return (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setScheduleVersion({ taskId: task.id, version: "" })}
          >
            Schedule
          </Button>
        );
      }
    }

    if (realm === "do") {
      if (task.status === "scheduled") {
        return (
          <Button size="sm" variant="outline" onClick={() => handleTaskAction(task.id, "start")}>
            Start
          </Button>
        );
      }
      if (task.status === "in_progress") {
        return (
          <div className="flex gap-1">
            <Button size="sm" variant="outline" onClick={() => handleTaskAction(task.id, "complete", { execution_log: "" })}>
              Complete
            </Button>
            <Button size="sm" variant="ghost" onClick={() => {
              const reason = prompt("Block reason:");
              if (reason) handleTaskAction(task.id, "block", { reason });
            }}>
              Block
            </Button>
          </div>
        );
      }
      if (task.status === "blocked") {
        return (
          <Button size="sm" variant="outline" onClick={() => handleTaskAction(task.id, "unblock")}>
            Unblock
          </Button>
        );
      }
    }

    return null;
  };

  // Project detail view
  if (selectedProject) {
    const nextRealm = getNextRealm(selectedProject.realm);

    return (
      <div className="flex-1 flex flex-col">
        <Header title={selectedProject.name} />

        <div className="p-6">
          <Button variant="ghost" onClick={() => setSelectedProject(null)} className="mb-4">
            <ArrowLeft className="h-4 w-4 mr-2" /> Back to Projects
          </Button>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500 text-red-500 text-sm">
              {error}
            </div>
          )}

          {/* Project Info */}
          <div className="mb-6 p-4 rounded-lg bg-muted">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold">{selectedProject.name}</h2>
                <RealmBadge realm={selectedProject.realm} />
              </div>
              {nextRealm && (
                <Button onClick={() => handleMoveRealm(nextRealm)}>
                  Move to {nextRealm.charAt(0).toUpperCase() + nextRealm.slice(1)}
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              )}
            </div>
            {selectedProject.repo && (
              <p className="text-sm text-muted-foreground">{selectedProject.repo}</p>
            )}
            {selectedProject.current_version && (
              <p className="text-sm">Version: {selectedProject.current_version}</p>
            )}
            <p className="text-xs text-muted-foreground mt-2">{selectedProject.realm_time}</p>
          </div>

          {/* Tasks */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Tasks ({selectedProject.tasks.length})</h3>
            {selectedProject.realm === "assess" && (
              <Button size="sm" onClick={() => setShowAddTask(!showAddTask)}>
                {showAddTask ? <X className="h-4 w-4 mr-1" /> : <Plus className="h-4 w-4 mr-1" />}
                {showAddTask ? "Cancel" : "Add Task"}
              </Button>
            )}
          </div>

          {/* Add Task Form */}
          {showAddTask && (
            <div className="mb-4 p-4 rounded-lg border border-border bg-muted/50">
              <div className="grid gap-3">
                <Input
                  placeholder="Task title"
                  value={newTask.title}
                  onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                />
                <textarea
                  placeholder="Description (optional)"
                  value={newTask.description}
                  onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                  className="w-full p-2 rounded-md border border-input bg-background text-sm min-h-[80px]"
                />
                <div className="flex gap-2">
                  <select
                    value={newTask.type}
                    onChange={(e) => setNewTask({ ...newTask, type: e.target.value })}
                    className="px-3 py-2 rounded-md border border-input bg-background text-sm"
                  >
                    <option value="feature">Feature</option>
                    <option value="bug">Bug</option>
                  </select>
                  <Button onClick={handleCreateTask} disabled={isCreating || !newTask.title.trim()}>
                    {isCreating ? "Creating..." : "Create Task"}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Schedule Version Modal */}
          {scheduleVersion && (
            <div className="mb-4 p-4 rounded-lg border border-primary bg-primary/10">
              <p className="text-sm mb-2">Schedule task to version:</p>
              <div className="flex gap-2">
                <Input
                  placeholder="e.g., 1.0.0"
                  value={scheduleVersion.version}
                  onChange={(e) => setScheduleVersion({ ...scheduleVersion, version: e.target.value })}
                />
                <Button onClick={handleScheduleTask} disabled={!scheduleVersion.version.trim()}>
                  Schedule
                </Button>
                <Button variant="ghost" onClick={() => setScheduleVersion(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {/* Task List */}
          {selectedProject.tasks.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No tasks yet. {selectedProject.realm === "assess" ? "Add tasks to define your project scope." : ""}
            </p>
          ) : (
            <div className="space-y-2">
              {selectedProject.tasks.map((task) => (
                <div
                  key={task.id}
                  className="p-3 rounded-lg border border-border bg-background flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    {statusIcons[task.status] || <Circle className="h-4 w-4" />}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{task.title}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${task.type === "bug" ? "bg-red-500/20 text-red-500" : "bg-blue-500/20 text-blue-500"}`}>
                          {task.type}
                        </span>
                        <span className="text-xs text-muted-foreground">{task.status}</span>
                      </div>
                      {task.description && (
                        <p className="text-sm text-muted-foreground">{task.description}</p>
                      )}
                      {task.version && (
                        <p className="text-xs text-muted-foreground">Version: {task.version}</p>
                      )}
                      {task.branch && (
                        <p className="text-xs text-muted-foreground">Branch: {task.branch}</p>
                      )}
                    </div>
                  </div>
                  {renderTaskActions(task)}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Project list view
  return (
    <div className="flex-1 flex flex-col">
      <Header title="Projects" />

      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex gap-2">
            <button
              onClick={() => setFilter(null)}
              className={`px-3 py-1 rounded-full text-sm ${
                filter === null ? "bg-primary text-primary-foreground" : "bg-muted"
              }`}
            >
              All
            </button>
            {["assess", "decide", "do"].map((realm) => (
              <button
                key={realm}
                onClick={() => setFilter(realm)}
                className={`px-3 py-1 rounded-full text-sm ${
                  filter === realm ? "bg-primary text-primary-foreground" : "bg-muted"
                }`}
              >
                {realm.charAt(0).toUpperCase() + realm.slice(1)}
              </button>
            ))}
          </div>
          <Button
            size="sm"
            onClick={() => setShowAddProject(!showAddProject)}
            variant={showAddProject ? "outline" : "default"}
          >
            {showAddProject ? <X className="h-4 w-4 mr-1" /> : <Plus className="h-4 w-4 mr-1" />}
            {showAddProject ? "Cancel" : "New Project"}
          </Button>
        </div>

        {showAddProject && (
          <div className="mb-6 p-4 rounded-lg border border-border bg-muted/50">
            <h3 className="font-medium mb-4">Create New Project</h3>
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <label className="text-sm text-muted-foreground block mb-1">Project Name *</label>
                <Input
                  placeholder="My Project"
                  value={newProject.name}
                  onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground block mb-1">Realm</label>
                <select
                  value={newProject.realm}
                  onChange={(e) => setNewProject({ ...newProject, realm: e.target.value })}
                  className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm"
                >
                  <option value="assess">Assess</option>
                  <option value="decide">Decide</option>
                  <option value="do">Do</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-muted-foreground block mb-1">Repository (optional)</label>
                <Input
                  placeholder="github.com/user/repo"
                  value={newProject.repo}
                  onChange={(e) => setNewProject({ ...newProject, repo: e.target.value })}
                />
              </div>
            </div>
            {error && <p className="text-sm text-red-500 mt-2">{error}</p>}
            <div className="mt-4 flex justify-end">
              <Button onClick={handleCreateProject} disabled={isCreating || !newProject.name.trim()}>
                {isCreating ? "Creating..." : "Create Project"}
              </Button>
            </div>
          </div>
        )}

        {isLoading ? (
          <p className="text-muted-foreground">Loading projects...</p>
        ) : projects.length === 0 ? (
          <div className="text-center py-12">
            <FolderKanban className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No projects yet.</p>
            <p className="text-sm text-muted-foreground mt-2">
              Click "New Project" to create your first project.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <div
                key={project.id}
                onClick={() => loadProjectDetails(project.id)}
                className="p-4 rounded-lg border border-border bg-background hover:bg-muted transition-colors cursor-pointer"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-medium">{project.name}</h3>
                  <RealmBadge realm={project.realm} size="sm" />
                </div>
                {project.current_version && (
                  <p className="text-sm text-muted-foreground">Version: {project.current_version}</p>
                )}
                {project.repo && (
                  <p className="text-xs text-muted-foreground truncate mt-1">{project.repo}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
