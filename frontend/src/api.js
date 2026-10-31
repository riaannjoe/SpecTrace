/**
 * SpecTrace API client.
 *
 * All API calls go through this module.  The base URL is read from the
 * VITE_API_BASE_URL environment variable (set in .env) so it is never
 * hard-coded here.
 *
 * Error format produced by the SpecTrace backend:
 *   { "error": { "code": "...", "message": "..." } }
 * or, for HTTP errors thrown by FastAPI before our handlers run:
 *   { "detail": "..." }
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8001").replace(/\/$/, "");

/**
 * Core fetch wrapper.  Throws an Error with the server's human-readable
 * message on any non-2xx response.
 */
async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, options);
  } catch (networkError) {
    throw new Error(
      "Cannot reach the SpecTrace backend. Is it running at " + BASE_URL + "?"
    );
  }

  // Try to parse JSON — some error responses may be empty.
  let data = {};
  try {
    data = await response.json();
  } catch {
    // Non-JSON body (e.g. 502 from a proxy).  data stays {}.
  }

  if (!response.ok) {
    // Backend custom error envelope
    const message =
      data?.error?.message ||
      // FastAPI default detail string / array
      (typeof data?.detail === "string"
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail.map((d) => d.msg).join("; ")
          : null) ||
      `HTTP ${response.status}`;
    throw new Error(message);
  }

  return data;
}

// ─── Health ──────────────────────────────────────────────────────────────────

/** GET /  →  { status, service, database, analysis_engine } */
export function healthCheck() {
  return request("/");
}

// ─── Projects ────────────────────────────────────────────────────────────────

/**
 * POST /projects/upload  (multipart/form-data)
 * @param {File}   file        A .zip archive
 * @param {string} projectName Optional human-readable name
 * @returns {Promise<ProjectOut>}
 */
export function uploadProject(file, projectName) {
  const form = new FormData();
  form.append("file", file);
  if (projectName && projectName.trim()) {
    form.append("project_name", projectName.trim());
  }
  // Do NOT set Content-Type manually — the browser must set the boundary.
  return request("/projects/upload", { method: "POST", body: form });
}

/**
 * GET /projects  →  { count, projects: ProjectOut[] }
 */
export function listProjects() {
  return request("/projects");
}

/**
 * GET /projects/{projectId}  →  ProjectOut
 */
export function getProject(projectId) {
  return request(`/projects/${projectId}`);
}

// ─── Requirements ────────────────────────────────────────────────────────────

/**
 * POST /projects/{projectId}/requirements
 * @param {string}   projectId
 * @param {string[]} requirements  Non-empty array of requirement strings
 * @param {boolean}  replace       True = replace existing requirements
 * @returns {Promise<RequirementsOut>}
 */
export function submitRequirements(projectId, requirements, replace = true) {
  return request(`/projects/${projectId}/requirements`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirements, replace }),
  });
}

/**
 * GET /projects/{projectId}/requirements  →  RequirementsOut
 */
export function getRequirements(projectId) {
  return request(`/projects/${projectId}/requirements`);
}

// ─── Analysis ────────────────────────────────────────────────────────────────

/**
 * POST /projects/{projectId}/analyze  →  ResultsOut
 * Analysis is synchronous on the backend; this call may take several seconds.
 */
export function analyzeProject(projectId) {
  return request(`/projects/${projectId}/analyze`, { method: "POST" });
}

/**
 * GET /projects/{projectId}/results  →  ResultsOut
 */
export function getResults(projectId) {
  return request(`/projects/${projectId}/results`);
}

