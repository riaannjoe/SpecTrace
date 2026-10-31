
import { useEffect, useState } from "react";
import {
  Code2, LayoutDashboard, Upload, FolderOpen, FileText,
  Search, CheckCircle2, AlertCircle, Clock, ArrowRight,
  ArrowLeft, Loader2, ShieldCheck,
  ChevronRight, FileCode2, Activity, X, Plus,
} from "lucide-react";

const API_URL = "http://localhost:8000";

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || data.message || "Something went wrong.");
  }

  return data;
}

function App() {
  const [page, setPage] = useState("dashboard");
  const [projects, setProjects] = useState([]);
  const [project, setProject] = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [projectName, setProjectName] = useState("");
  const [file, setFile] = useState(null);
  const [requirementsText, setRequirementsText] = useState("");

  async function loadProjects() {
    try {
      const data = await apiRequest("/projects");
      setProjects(Array.isArray(data) ? data : data.projects || []);
    } catch (err) {
      console.error(err);
    }
  }

  useEffect(() => {
    loadProjects();
  }, []);

  function navigate(nextPage) {
    setError("");
    setPage(nextPage);
  }

  async function handleUpload(event) {
    event.preventDefault();

    if (!file) {
      setError("Please select a ZIP file first.");
      return;
    }

    if (!file.name.toLowerCase().endsWith(".zip")) {
      setError("Please upload a ZIP file.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      if (projectName.trim()) {
        formData.append("project_name", projectName.trim());
      }

      const uploaded = await apiRequest("/projects/upload", {
        method: "POST",
        body: formData,
      });

      setProject(uploaded);
      setFile(null);
      setProjectName("");
      await loadProjects();
      setPage("requirements");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function saveRequirements(event) {
    event.preventDefault();

    const requirements = requirementsText
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);

    if (!requirements.length) {
      setError("Enter at least one requirement.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await apiRequest(`/projects/${project.id}/requirements`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          requirements,
          replace: true,
        }),
      });

      setPage("ready");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function runAnalysis() {
    setLoading(true);
    setError("");

    try {
      await apiRequest(`/projects/${project.id}/analyze`, {
        method: "POST",
      });

      const data = await apiRequest(`/projects/${project.id}/results`);
      setResults(data);
      await loadProjects();
      setPage("results");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function openProject(item) {
    setLoading(true);
    setError("");

    try {
      setProject(item);
      const data = await apiRequest(`/projects/${item.id}/results`);
      setResults(data);
      setPage("results");
    } catch (err) {
      setError("Could not load this project's results. It may not have been analyzed yet.");
      setPage("dashboard");
    } finally {
      setLoading(false);
    }
  }

  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "upload", label: "New Project", icon: Upload },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand" onClick={() => navigate("dashboard")}>
          <div className="brand-icon"><Code2 size={22} /></div>
          <span>Spec<span className="gradient-text">Trace</span></span>
        </div>

        <div className="side-label">WORKSPACE</div>

        <nav className="side-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`nav-item ${page === item.id ? "active" : ""}`}
                onClick={() => navigate(item.id)}
              >
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-tip">
            <ShieldCheck size={20} />
            <strong>Requirement intelligence</strong>
            <p>Understand how your project relates to its specifications.</p>
          </div>
          <div className="side-footer">SpecTrace · Project workspace</div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <ChevronRight size={15} />
            <strong>
              {page === "dashboard" ? "Dashboard" :
               page === "upload" ? "New project" :
               page === "requirements" ? "Requirements" :
               page === "ready" ? "Analysis" : "Results"}
            </strong>
          </div>
          <div className="topbar-status">
            <span className="status-dot" /> System workspace
          </div>
        </header>

        <div className="content">
          {error && (
            <div className="error-banner">
              <AlertCircle size={18} />
              <span>{error}</span>
              <button onClick={() => setError("")}><X size={16} /></button>
            </div>
          )}

          {page === "dashboard" && (
            <Dashboard
              projects={projects}
              onUpload={() => navigate("upload")}
              onOpen={openProject}
            />
          )}

          {page === "upload" && (
            <UploadPage
              projectName={projectName}
              setProjectName={setProjectName}
              file={file}
              setFile={setFile}
              loading={loading}
              onSubmit={handleUpload}
              onBack={() => navigate("dashboard")}
            />
          )}

          {page === "requirements" && project && (
            <RequirementsPage
              project={project}
              value={requirementsText}
              setValue={setRequirementsText}
              loading={loading}
              onSubmit={saveRequirements}
              onBack={() => navigate("upload")}
            />
          )}

          {page === "ready" && project && (
            <ReadyPage
              project={project}
              loading={loading}
              onAnalyze={runAnalysis}
              onBack={() => navigate("requirements")}
            />
          )}

          {page === "results" && results && (
            <ResultsPage
              results={results}
              project={project}
              onBack={() => navigate("dashboard")}
              onNew={() => navigate("upload")}
            />
          )}

          {loading && page === "dashboard" && (
            <div className="loading-overlay">
              <Loader2 className="spin" size={24} />
              Loading project...
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function Dashboard({ projects, onUpload, onOpen }) {
  const total = projects.length;

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow"><Activity size={14} /> SOFTWARE REQUIREMENT INTELLIGENCE</div>
          <h1>Know what your code <span className="gradient-text">actually does.</span></h1>
          <p className="muted">Upload your project, define its requirements, and inspect the analysis results.</p>
        </div>
        <button className="primary-btn" onClick={onUpload}>
          <Plus size={18} /> New project
        </button>
      </section>

      <section className="stats-grid">
        <StatCard icon={FolderOpen} label="Total projects" value={total} />
        <StatCard icon={FileCode2} label="Projects analyzed" value={projects.filter(p => p.status === "analyzed").length} />
        <StatCard icon={Clock} label="Workspace" value="Active" />
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Your projects</h2>
            <p className="muted">Projects you have uploaded to SpecTrace.</p>
          </div>
          <button className="outline-btn" onClick={onUpload}><Upload size={16} /> Upload project</button>
        </div>

        {projects.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"><FolderOpen size={30} /></div>
            <h3>No projects yet</h3>
            <p>Upload a Python project ZIP to get started.</p>
            <button className="primary-btn" onClick={onUpload}><Upload size={17} /> Upload your first project</button>
          </div>
        ) : (
          <div className="project-list">
            {projects.map((p) => (
              <div className="project-row" key={p.id}>
                <div className="project-file-icon"><Code2 size={21} /></div>
                <div className="project-info">
                  <strong>{p.project_name || p.filename}</strong>
                  <span>{p.filename} · {p.python_file_count ?? 0} Python files</span>
                </div>
                <span className={`project-status ${p.status === "analyzed" ? "done" : ""}`}>{p.status || "Uploaded"}</span>
                <button className="icon-btn" onClick={() => onOpen(p)} title="Open project"><ArrowRight size={18} /></button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="steps-grid">
        <StepCard number="01" title="Upload project" text="Upload your source code in a ZIP archive." />
        <StepCard number="02" title="Define requirements" text="Add the features and conditions your project should meet." />
        <StepCard number="03" title="Review results" text="Inspect requirement statuses and available code evidence." />
      </section>
    </>
  );
}

function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-icon"><Icon size={19} /></div>
      <div><span>{label}</span><strong>{value}</strong></div>
    </div>
  );
}

function StepCard({ number, title, text }) {
  return (
    <div className="step-card">
      <span>{number}</span>
      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}

function UploadPage({ projectName, setProjectName, file, setFile, loading, onSubmit, onBack }) {
  return (
    <section className="form-page">
      <button className="back-btn" onClick={onBack}><ArrowLeft size={16} /> Back to dashboard</button>
      <div className="eyebrow">STEP 01 / PROJECT UPLOAD</div>
      <h1>Upload your <span className="gradient-text">project.</span></h1>
      <p className="muted">Start by uploading a ZIP archive containing your Python source code.</p>

      <form className="panel form-panel" onSubmit={onSubmit}>
        <label>Project name <span className="optional">OPTIONAL</span></label>
        <input
          className="text-input"
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          placeholder="e.g. Student Management System"
        />

        <label>Project ZIP file</label>
        <label className="dropzone">
          <input
            type="file"
            accept=".zip,application/zip"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            hidden
          />
          <div className="upload-icon"><Upload size={27} /></div>
          <strong>{file ? file.name : "Choose a ZIP file"}</strong>
          <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "Click here to browse your files"}</span>
          <small>ZIP archive · Maximum size 50 MB</small>
        </label>

        <div className="form-actions">
          <button type="button" className="outline-btn" onClick={onBack}>Cancel</button>
          <button className="primary-btn" disabled={loading || !file}>
            {loading ? <><Loader2 className="spin" size={17} /> Uploading...</> : <>Upload project <ArrowRight size={17} /></>}
          </button>
        </div>
      </form>
    </section>
  );
}

function RequirementsPage({ project, value, setValue, loading, onSubmit, onBack }) {
  return (
    <section className="form-page">
      <button className="back-btn" onClick={onBack}><ArrowLeft size={16} /> Back</button>
      <div className="eyebrow">STEP 02 / REQUIREMENTS</div>
      <h1>What should your <span className="gradient-text">code do?</span></h1>
      <p className="muted">Add each software requirement on a separate line.</p>

      <div className="uploaded-file">
        <FileCode2 size={21} />
        <div><strong>{project.project_name || project.filename}</strong><span>{project.filename}</span></div>
        <CheckCircle2 size={19} className="success-icon" />
      </div>

      <form className="panel form-panel" onSubmit={onSubmit}>
        <label>Project requirements</label>
        <textarea
          className="requirements-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={"Example:\nThe system should allow users to register.\nThe system should validate user login credentials.\nThe system should allow users to book tickets.\nThe system should store booking details."}
          rows={9}
        />
        <div className="input-hint">Enter one requirement per line. Empty lines will be ignored.</div>
        <div className="form-actions">
          <button type="button" className="outline-btn" onClick={onBack}>Back</button>
          <button className="primary-btn" disabled={loading || !value.trim()}>
            {loading ? <><Loader2 className="spin" size={17} /> Saving...</> : <>Save requirements <ArrowRight size={17} /></>}
          </button>
        </div>
      </form>
    </section>
  );
}

function ReadyPage({ project, loading, onAnalyze, onBack }) {
  return (
    <section className="form-page">
      <button className="back-btn" onClick={onBack}><ArrowLeft size={16} /> Edit requirements</button>
      <div className="ready-card">
        <div className="ready-icon"><ShieldCheck size={35} /></div>
        <div className="eyebrow">STEP 03 / READY TO ANALYZE</div>
        <h1>Your project is <span className="gradient-text">ready.</span></h1>
        <p className="muted">Your project and requirements have been saved. Start the analysis to view the report.</p>
        <div className="ready-project">
          <Code2 size={22} />
          <div><strong>{project.project_name || project.filename}</strong><span>{project.filename}</span></div>
          <CheckCircle2 className="success-icon" />
        </div>
        <button className="primary-btn wide-btn" onClick={onAnalyze} disabled={loading}>
          {loading ? <><Loader2 className="spin" size={18} /> Analyzing...</> : <>Run analysis <Search size={18} /></>}
        </button>
      </div>
    </section>
  );
}

function ResultsPage({ results, project, onBack, onNew }) {
  const summary = results.summary || {};
  const items = results.results || [];
  const isMock = results.is_mock;

  const statusLabel = {
    implemented: "Implemented",
    partially_implemented: "Partially implemented",
    missing: "Missing",
    not_verified: "Not verified",
  };

  return (
    <section>
      <button className="back-btn" onClick={onBack}><ArrowLeft size={16} /> Back to dashboard</button>
      <div className="results-heading">
        <div>
          <div className="eyebrow">ANALYSIS REPORT</div>
          <h1>{results.project_name || project?.project_name || "Project results"}</h1>
          <p className="muted">Review the status of each submitted requirement.</p>
        </div>
        <button className="primary-btn" onClick={onNew}><Plus size={17} /> New project</button>
      </div>

      {isMock && (
        <div className="demo-banner">
          <AlertCircle size={19} />
          <div><strong>Demo results – real analysis engine not connected</strong><span>These are placeholder results. They do not confirm that your code implements or passes the requirements.</span></div>
        </div>
      )}

      <div className="stats-grid result-stats">
        <StatCard icon={FileText} label="Total requirements" value={summary.total ?? items.length} />
        <StatCard icon={CheckCircle2} label="Implemented" value={summary.implemented ?? 0} />
        <StatCard icon={AlertCircle} label="Partially implemented" value={summary.partially_implemented ?? 0} />
        <StatCard icon={X} label="Missing" value={summary.missing ?? 0} />
      </div>

      <section className="panel">
        <div className="panel-heading">
          <div><h2>Requirement breakdown</h2><p className="muted">Individual status and available evidence.</p></div>
          <span className="result-count">{items.length} items</span>
        </div>

        {items.length === 0 ? (
          <div className="empty-state"><p>No result details were returned by the backend.</p></div>
        ) : (
          <div className="result-list">
            {items.map((item, index) => (
              <article className="result-item" key={index}>
                <div className="result-number">{String(index + 1).padStart(2, "0")}</div>
                <div className="result-content">
                  <strong>{item.requirement}</strong>
                  <span className={`result-badge ${item.status || "not_verified"}`}>
                    {statusLabel[item.status] || item.status || "Not verified"}
                  </span>
                  {item.explanation && <p>{item.explanation}</p>}
                  {item.evidence && item.evidence.length > 0 && (
                    <div className="evidence-list">
                      {item.evidence.map((e, i) => (
                        <div className="evidence" key={i}>
                          <FileCode2 size={15} />
                          <span>{e.file}{e.line ? ` : line ${e.line}` : ""}</span>
                          {e.description && <small>{e.description}</small>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}

export default App;
