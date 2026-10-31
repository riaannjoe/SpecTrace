import { useState } from "react";
import { Upload, FileArchive, X, ArrowRight } from "lucide-react";

export default function UploadProject({ onUpload, loading, loadingState }) {
  const [file, setFile] = useState(null);
  const [projectName, setProjectName] = useState("");

  function handleFileChange(event) {
    const selected = event.target.files[0];

    if (selected && !selected.name.toLowerCase().endsWith(".zip")) {
      alert("Please select a ZIP file.");
      event.target.value = "";
      return;
    }

    setFile(selected || null);
  }

  function handleSubmit(event) {
    event.preventDefault();

    if (!file) {
      alert("Please select a ZIP file first.");
      return;
    }

    onUpload(file, projectName);
  }

  const buttonLabel =
    loadingState === "uploading" ? "Uploading…" : "Upload Project";

  return (
    <div className="page-content">
      <div className="welcome-section">
        <div>
          <h2>Upload Python Project</h2>
          <p>Upload your project as a ZIP file to begin requirement analysis.</p>
        </div>
      </div>

      <form className="upload-card" onSubmit={handleSubmit}>
        <div className="upload-icon">
          <Upload size={30} />
        </div>

        <h2>Upload your project</h2>
        <p>Select a ZIP archive containing your Python project files.</p>

        <label className="upload-dropzone">
          <FileArchive size={36} />
          <strong>{file ? file.name : "Choose a ZIP file"}</strong>
          <span>
            {file ? "File selected" : "Click here to browse your computer"}
          </span>
          <input
            type="file"
            accept=".zip,application/zip"
            onChange={handleFileChange}
            hidden
          />
        </label>

        {file && (
          <div className="selected-file">
            <FileArchive size={18} />
            <span>{file.name}</span>
            <button
              type="button"
              className="icon-button"
              onClick={() => setFile(null)}
              aria-label="Remove selected file"
            >
              <X size={18} />
            </button>
          </div>
        )}

        <div className="form-group">
          <label htmlFor="projectName">Project Name (optional)</label>
          <input
            id="projectName"
            type="text"
            placeholder="Enter your project name"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
          />
        </div>

        <button
          type="submit"
          className="primary-button upload-submit"
          disabled={loading || !file}
        >
          {buttonLabel}
          <ArrowRight size={18} />
        </button>

        <p className="upload-note">
          Only ZIP files are accepted. Maximum size depends on server settings.
        </p>
      </form>
    </div>
  );
}
