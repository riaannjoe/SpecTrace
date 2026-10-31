import { useState } from "react";
import {
  ArrowRight,
  Code2,
  Upload,
  FileArchive,
  ShieldCheck,
  ScanSearch,
  GitBranch,
  Loader2,
  CheckCircle2,
  AlertCircle,
  X,
} from "lucide-react";

const API_URL = "http://localhost:8000";

function App() {
  const [page, setPage] = useState("home");
  const [projectName, setProjectName] = useState("");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploadedProject, setUploadedProject] = useState(null);

  async function handleUpload(e) {
    e.preventDefault();
    setError("");

    if (!file) {
      setError("Please select a ZIP file first.");
      return;
    }

    if (!file.name.toLowerCase().endsWith(".zip")) {
      setError("Please upload a .zip file.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    if (projectName.trim()) {
      formData.append("project_name", projectName.trim());
    }

    try {
      setLoading(true);

      const response = await fetch(`${API_URL}/projects/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed. Please try again.");
      }

      setUploadedProject(data);
    } catch (err) {
      setError(
        err.message === "Failed to fetch"
          ? "Cannot connect to the backend. Make sure your FastAPI server is running."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  }

  function resetUpload() {
    setFile(null);
    setProjectName("");
    setUploadedProject(null);
    setError("");
  }

  return (
    <div className="min-h-screen bg-[#080b14] text-white">
      {/* Navigation */}
      <nav className="flex items-center justify-between border-b border-white/10 px-6 py-5 md:px-12">
        <button
          onClick={() => {
            setPage("home");
            resetUpload();
          }}
          className="flex items-center gap-3"
        >
          <div className="rounded-xl border border-violet-400/30 bg-violet-500/15 p-2">
            <Code2 className="text-violet-300" size={25} />
          </div>
          <span className="text-xl font-bold">
            Spec<span className="text-violet-400">Trace</span>
          </span>
        </button>

        <div className="flex items-center gap-5 text-sm text-slate-400">
          <button onClick={() => setPage("home")} className="hover:text-white">
            Home
          </button>
          <button
            onClick={() => setPage("upload")}
            className="rounded-lg bg-violet-600 px-4 py-2 font-semibold text-white hover:bg-violet-500"
          >
            Start Analysis
          </button>
        </div>
      </nav>

      {page === "home" ? (
        /* HOME PAGE */
        <main className="mx-auto max-w-7xl px-6 py-24 md:px-12">
          <div className="grid items-center gap-16 lg:grid-cols-2">
            <div>
              <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-violet-400/20 bg-violet-400/10 px-4 py-2 text-xs text-violet-200">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                SOFTWARE REQUIREMENT INTELLIGENCE
              </div>

              <h1 className="text-5xl font-bold leading-tight sm:text-6xl">
                Does your code actually meet{" "}
                <span className="gradient-text">the specs?</span>
              </h1>

              <p className="mt-7 max-w-xl text-lg leading-8 text-slate-400">
                Stop guessing. Start verifying. SpecTrace connects software
                requirements to code evidence, helping you understand what
                your project really implements.
              </p>

              <button
                onClick={() => setPage("upload")}
                className="mt-9 flex items-center gap-3 rounded-xl bg-violet-600 px-7 py-4 font-semibold shadow-lg shadow-violet-600/20 hover:bg-violet-500"
              >
                Start your analysis <ArrowRight size={19} />
              </button>

              <div className="mt-10 flex flex-wrap gap-6 text-sm text-slate-400">
                <span className="flex items-center gap-2">
                  <CheckCircle2 className="text-emerald-400" size={17} />
                  Requirement analysis
                </span>
                <span className="flex items-center gap-2">
                  <CheckCircle2 className="text-emerald-400" size={17} />
                  Code traceability
                </span>
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-[#101626] p-7 shadow-2xl shadow-violet-950/30">
              <p className="text-sm font-semibold text-violet-300">
                HOW SPECTRACE WORKS
              </p>

              {[
                {
                  icon: Upload,
                  title: "Upload your project",
                  desc: "Provide your Python project as a ZIP file.",
                },
                {
                  icon: ScanSearch,
                  title: "Add requirements",
                  desc: "Tell us what your software is supposed to do.",
                },
                {
                  icon: GitBranch,
                  title: "Explore traceability",
                  desc: "View the analysis results and code evidence.",
                },
              ].map((item, index) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.title}
                    className="mt-7 flex items-start gap-4"
                  >
                    <div className="rounded-xl bg-violet-500/15 p-3">
                      <Icon className="text-violet-300" size={23} />
                    </div>
                    <div>
                      <p className="font-semibold">{item.title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-400">
                        {item.desc}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </main>
      ) : (
        /* UPLOAD PAGE */
        <main className="mx-auto max-w-3xl px-6 py-16">
          <button
            onClick={() => {
              setPage("home");
              resetUpload();
            }}
            className="mb-8 text-sm text-slate-400 hover:text-white"
          >
            ← Back to home
          </button>

          <div className="mb-9">
            <p className="text-sm font-semibold tracking-widest text-violet-400">
              STEP 01 — PROJECT SETUP
            </p>
            <h1 className="mt-3 text-4xl font-bold">
              Upload your project
            </h1>
            <p className="mt-3 leading-7 text-slate-400">
              Start by providing your Python project. We'll prepare it for
              requirement analysis.
            </p>
          </div>

          {!uploadedProject ? (
            <form
              onSubmit={handleUpload}
              className="rounded-2xl border border-white/10 bg-[#101626] p-6 sm:p-9"
            >
              <label className="mb-2 block text-sm font-medium">
                Project name
              </label>

              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="e.g. Student Management System"
                className="mb-7 w-full rounded-xl border border-white/10 bg-[#080d18] px-4 py-3 text-white outline-none focus:border-violet-400"
              />

              <label className="mb-3 block text-sm font-medium">
                Upload ZIP file
              </label>

              <label className="flex min-h-52 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-violet-400/30 bg-violet-400/[0.04] p-6 text-center transition hover:border-violet-400/70">
                <FileArchive size={42} className="mb-4 text-violet-300" />

                {file ? (
                  <>
                    <p className="font-semibold text-emerald-300">
                      {file.name}
                    </p>
                    <p className="mt-2 text-xs text-slate-400">
                      {(file.size / (1024 * 1024)).toFixed(2)} MB
                    </p>
                  </>
                ) : (
                  <>
                    <p className="font-semibold">
                      Click to select your project
                    </p>
                    <p className="mt-2 text-sm text-slate-400">
                      Python project ZIP files only
                    </p>
                  </>
                )}

                <input
                  type="file"
                  accept=".zip,application/zip"
                  className="hidden"
                  onChange={(e) => {
                    setFile(e.target.files[0] || null);
                    setError("");
                  }}
                />
              </label>

              {file && (
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  className="mt-3 flex items-center gap-1 text-xs text-slate-400 hover:text-white"
                >
                  <X size={14} /> Remove file
                </button>
              )}

              {error && (
                <div className="mt-5 flex items-start gap-2 rounded-lg border border-red-400/20 bg-red-400/10 p-3 text-sm text-red-300">
                  <AlertCircle size={18} className="shrink-0" />
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="mt-7 flex w-full items-center justify-center gap-3 rounded-xl bg-violet-600 px-6 py-4 font-semibold hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? (
                  <>
                    <Loader2 className="animate-spin" size={19} />
                    Uploading project...
                  </>
                ) : (
                  <>
                    Upload project <ArrowRight size={19} />
                  </>
                )}
              </button>

              <p className="mt-4 text-center text-xs text-slate-500">
                Your project must be compressed into a .zip file.
              </p>
            </form>
          ) : (
            <div className="rounded-2xl border border-emerald-400/20 bg-[#101626] p-8">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="text-emerald-400" size={32} />
                <div>
                  <h2 className="text-xl font-bold">Upload successful!</h2>
                  <p className="mt-1 text-sm text-slate-400">
                    Your project has been received.
                  </p>
                </div>
              </div>

              <div className="mt-7 space-y-4 rounded-xl bg-[#080d18] p-5 text-sm">
                <div>
                  <p className="text-slate-500">Project name</p>
                  <p className="mt-1 font-medium">
                    {uploadedProject.project_name}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Project ID</p>
                  <p className="mt-1 break-all font-mono text-violet-300">
                    {uploadedProject.id}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Python files detected</p>
                  <p className="mt-1 font-medium">
                    {uploadedProject.python_file_count}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Status</p>
                  <p className="mt-1 font-medium text-emerald-300">
                    {uploadedProject.status}
                  </p>
                </div>
              </div>

              <p className="mt-5 text-sm text-slate-400">
                Next, we'll add the software requirements for this project.
              </p>

              <button
                onClick={() =>
                  alert("The requirements page will be added in the next step.")
                }
                className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 px-6 py-4 font-semibold hover:bg-violet-500"
              >
                Continue <ArrowRight size={18} />
              </button>
            </div>
          )}
        </main>
      )}

      <footer className="border-t border-white/10 px-6 py-7 text-center text-xs text-slate-500">
        SpecTrace — Making software requirements traceable.
      </footer>
    </div>
  );
}

export default App;