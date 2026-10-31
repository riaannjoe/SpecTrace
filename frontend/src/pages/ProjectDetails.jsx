
import {
  FolderOpen,
  FileCode2,
  Calendar,
  ArrowLeft,
  Play,
  FileText,
} from "lucide-react";

export default function ProjectDetails({
  project,
  onBack,
  onAddRequirements,
  onAnalyze,
}) {
  if (!project) {
    return (
      <div className="page-content">
        <p>No project selected.</p>
        <button className="secondary-button" onClick={onBack}>
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="page-content">
      <div className="welcome-section">
        <div>
          <h2>Project Details</h2>
          <p>View information about your uploaded project.</p>
        </div>

        <button className="secondary-button" onClick={onBack}>
          <ArrowLeft size={17} />
          Back
        </button>
      </div>

      <div className="details-card">
        <div className="details-title">
          <div className="project-icon">
            <FolderOpen size={26} />
          </div>
          <div>
            <h2>{project.project_name}</h2>
            <span className="project-status">
              {project.status || "uploaded"}
            </span>
          </div>
        </div>

        <div className="details-grid">
          <div className="detail-item">
            <FileText size={20} />
            <div>
              <span>Uploaded file</span>
              <strong>{project.filename || "Not available"}</strong>
            </div>
          </div>

          <div className="detail-item">
            <FileCode2 size={20} />
            <div>
              <span>Python files</span>
              <strong>{project.python_file_count ?? 0}</strong>
            </div>
          </div>

          <div className="detail-item">
            <FolderOpen size={20} />
            <div>
              <span>Total files</span>
              <strong>{project.total_file_count ?? 0}</strong>
            </div>
          </div>

          <div className="detail-item">
            <Calendar size={20} />
            <div>
              <span>Created at</span>
              <strong>
                {project.created_at
                  ? new Date(project.created_at).toLocaleString()
                  : "Not available"}
              </strong>
            </div>
          </div>
        </div>

        <div className="details-actions">
          <button className="secondary-button" onClick={onAddRequirements}>
            <FileText size={18} />
            Manage Requirements
          </button>

          <button className="primary-button" onClick={onAnalyze}>
            <Play size={18} />
            Run Analysis
          </button>
        </div>
      </div>
    </div>
  );
}
