// Drop this into the React project (e.g. src/api.js). Uses plain fetch - no extra libraries.
const BASE_URL = "http://localhost:8000";

// Every error from the backend looks like: { error: { code, message, details? } }
async function handle(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.error?.message || `Request failed (${res.status})`);
  return data;
}

// 1) Upload a ZIP  ->  returns { id, project_name, ... }
export async function uploadProject(file, projectName) {
  const form = new FormData();
  form.append("file", file);                         // <input type="file" accept=".zip">
  if (projectName) form.append("project_name", projectName);
  return handle(await fetch(`${BASE_URL}/projects/upload`, { method: "POST", body: form }));
  // NOTE: do NOT set Content-Type yourself for FormData - the browser adds the boundary.
}

// 2) Submit requirements (array of strings)
export async function addRequirements(projectId, requirements, replace = false) {
  return handle(await fetch(`${BASE_URL}/projects/${projectId}/requirements`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirements, replace }),
  }));
}

// 3) "Analyse Project" button -> returns the full results object
export async function analyzeProject(projectId) {
  return handle(await fetch(`${BASE_URL}/projects/${projectId}/analyze`, { method: "POST" }));
}

// 4) Re-fetch stored results any time
export async function getResults(projectId) {
  return handle(await fetch(`${BASE_URL}/projects/${projectId}/results`));
}

export async function listProjects() {
  return handle(await fetch(`${BASE_URL}/projects`));
}

// Show a banner when results.is_mock === true: "Demo data - real analysis engine not connected".
