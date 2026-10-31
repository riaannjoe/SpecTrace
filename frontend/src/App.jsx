
import { useEffect, useState } from "react";

import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";

import Dashboard from "./pages/Dashboard";
import UploadProject from "./pages/UploadProject";
import Requirements from "./pages/Requirements";
import Results from "./pages/Results";
import ProjectDetails from "./pages/ProjectDetails";

const API_URL = "http://localhost:8000";

export default function App() {
  const [activePage, setActivePage] = useState("Dashboard");
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function apiRequest(url, options = {}) {
    const response = await fetch(`${API_URL}${url}`, options);

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.detail || "Something went wrong.");
    }

    return data;
  }

  async function loadProjects() {
    try {
      const data = await apiRequest("/projects");
      setProjects(Array.isArray(data) ? data : data.projects || []);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadProjects();
  }, []);

  async function handleUpload(file, projectName) {
    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      if (projectName.trim()) {
        formData.append("project_name", projectName.trim());
      }

      const uploadedProject = await apiRequest("/projects/upload", {
        method: "POST",
        body: formData,
      });

      setProject(uploadedProject);
      await loadProjects();
      setActivePage("Requirements");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveRequirements(requirements) {
    if (!project) return;

    setLoading(true);
    setError("");

    try {
      await apiRequest(`/projects/${project.id}/requirements`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          requirements,
          replace: true,
        }),
      });

      await handleAnalyze(project);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  }

  async function handleAnalyze(selectedProject) {
    if (!selectedProject) return;

    setLoading(true);
    setError("");

    try {
      setProject(selectedProject);

      await apiRequest(
        `/projects/${selectedProject.id}/analyze`,
        { method: "POST" }
      );

      const analysisResults = await apiRequest(
        `/projects/${selectedProject.id}/results`
      );

      setResults(analysisResults);
      setActivePage("Results");
      await loadProjects();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleOpenProject(selectedProject) {
    setProject(selectedProject);
    setResults(null);
    setError("");

    try {
      const existingResults = await apiRequest(
        `/projects/${selectedProject.id}/results`
      );

      setResults(existingResults);
      setActivePage("Results");
    } catch {
      setActivePage("Project Details");
    }
  }

  function renderPage() {
    switch (activePage) {
      case "Dashboard":
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
          />
        );

      case "Requirements":
        return (
          <Requirements
            project={project}
            onSubmit={handleSaveRequirements}
            loading={loading}
          />
        );

      case "Results":
        return (
          <Results
            results={results}
            onBack={() => setActivePage("Dashboard")}
          />
        );

      case "Project Details":
        return (
          <ProjectDetails
            project={project}
            onBack={() => setActivePage("Dashboard")}
            onAddRequirements={() => setActivePage("Requirements")}
            onAnalyze={() => handleAnalyze(project)}
          />
        );

      case "Projects":
        return (
          <Dashboard
            projects={projects}
            onUpload={() => setActivePage("Upload Project")}
            onOpenProject={handleOpenProject}
          />
        );

      default:
        return <Dashboard projects={projects} />;
    }
  }

  return (
    <div className="app-layout">
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
      />

      <main className="main-content">
        <Navbar title={activePage} />

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
