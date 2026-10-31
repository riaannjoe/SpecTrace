import { useEffect, useRef, useState } from "react";

import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";

import Dashboard from "./pages/Dashboard";
import UploadProject from "./pages/UploadProject";
import Requirements from "./pages/Requirements";
import Results from "./pages/Results";
import ProjectDetails from "./pages/ProjectDetails";

import {
  listProjects,
  uploadProject,
  submitRequirements,
  analyzeProject,
  getResults,
} from "./api";

export default function App() {
  const [activePage, setActivePage] = useState("Dashboard");
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState(null);
  const [results, setResults] = useState(null);
  // "idle" | "uploading" | "saving" | "analyzing"
  const [loadingState, setLoadingState] = useState("idle");
  const [error, setError] = useState("");

  // Prevent duplicate analysis submissions (e.g. double-click or StrictMode).
  const analyzingRef = useRef(false);

  const loading = loadingState !== "idle";

  async function loadProjects() {
    try {
      const data = await listProjects();
      setProjects(Array.isArray(data) ? data : data.projects ?? []);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadProjects();
  }, []);

  async function handleUpload(file, projectName) {
    setLoadingState("uploading");
    setError("");

    try {
      const uploaded = await uploadProject(file, projectName);
      setProject(uploaded);
      await loadProjects();
      setActivePage("Requirements");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingState("idle");
    }
  }

  async function handleSaveRequirements(requirementTexts) {
    if (!project) return;

    setLoadingState("saving");
    setError("");

    try {
      await submitRequirements(project.id, requirementTexts, true);
      // Requirements saved — immediately run analysis.
      await runAnalysis(project);
    } catch (err) {
      setError(err.message);
      setLoadingState("idle");
    }
  }

  /** Shared analysis runner used from Requirements page and Project Details page. */
  async function runAnalysis(selectedProject) {
    if (!selectedProject) return;
    if (analyzingRef.current) return; // guard against duplicate clicks

    analyzingRef.current = true;
    setLoadingState("analyzing");
    setError("");
    setProject(selectedProject);

    try {
      // POST /analyze is synchronous — it returns the ResultsOut directly.
      const analysisResults = await analyzeProject(selectedProject.id);
      setResults(analysisResults);
      setActivePage("Results");
      await loadProjects();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingState("idle");
      analyzingRef.current = false;
    }
  }

  async function handleOpenProject(selectedProject) {
    setProject(selectedProject);
    setResults(null);
    setError("");

    try {
      const existingResults = await getResults(selectedProject.id);
      setResults(existingResults);
      setActivePage("Results");
    } catch {
      // No results yet — show project details so the user can run analysis.
      setActivePage("Project Details");
    }
  }

  function renderPage() {
    switch (activePage) {
      case "Dashboard":
      case "Projects":
        return (
          <Dashboard
            projects={projects}
            onUpload={() => setActivePage("Upload Project")}
            onOpenProject={handleOpenProject}
          />
        );

      case "Upload Project":
        return (
          <UploadProject
            onUpload={handleUpload}
            loading={loading}
            loadingState={loadingState}
          />
        );

      case "Requirements":
        return (
          <Requirements
            project={project}
            onSubmit={handleSaveRequirements}
            loading={loading}
            loadingState={loadingState}
          />
        );

      case "Results":
        return (
          <Results
            results={results}
            project={project}
            onBack={() => setActivePage("Dashboard")}
            onReanalyze={() => runAnalysis(project)}
            loading={loading}
            loadingState={loadingState}
          />
        );

      case "Project Details":
        return (
          <ProjectDetails
            project={project}
            onBack={() => setActivePage("Dashboard")}
            onAddRequirements={() => setActivePage("Requirements")}
            onAnalyze={() => runAnalysis(project)}
            loading={loading}
            loadingState={loadingState}
          />
        );

      default:
        return (
          <Dashboard
            projects={projects}
            onUpload={() => setActivePage("Upload Project")}
            onOpenProject={handleOpenProject}
          />
        );
    }
  }

  return (
    <div className="app-layout">
      <Sidebar activePage={activePage} setActivePage={setActivePage} />

      <main className="main-content">
        <Navbar title={activePage} loadingState={loadingState} />

        {error && (
          <div className="error-banner">
            {error}
            <button onClick={() => setError("")}>×</button>
          </div>
        )}

        {renderPage()}
      </main>
    </div>
  );
}
