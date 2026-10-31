
import {
  FolderOpen,
  FileCode2,
  CheckCircle2,
  AlertCircle,
  ArrowUpRight,
  Upload,
  Clock,
} from "lucide-react";

export default function Dashboard({ projects = [], onUpload, onOpenProject }) {
  const totalProjects = projects.length;

  const totalFiles = projects.reduce(
    (sum, project) => sum + (project.python_file_count || 0),
    0
  );

  const analyzedProjects = projects.filter(
    (project) => project.status === "analyzed"
  ).length;

  const stats = [
    {
      title: "Total Projects",
      value: totalProjects,
      icon: FolderOpen,
    },
    {
      title: "Python Files",
      value: totalFiles,
      icon: FileCode2,
    },
    {
      title: "Analyzed Projects",
      value: analyzedProjects,
      icon: CheckCircle2,
    },
  ];

  return (
    <div className="page-content">
      <div className="welcome-section">
        <div>
          <h2>Project Overview</h2>
          <p>
            Upload your Python projects and verify their software requirements.
          </p>
        </div>

        <button className="primary-button" onClick={onUpload}>
          <Upload size={18} />
          Upload Project
        </button>
      </div>

      <div className="stats-grid">
        {stats.map((stat) => {
          const Icon = stat.icon;

          return (
            <div className="stat-card" key={stat.title}>
              <div className="stat-icon">
                <Icon size={22} />
              </div>
              <p>{stat.title}</p>
              <h2>{stat.value}</h2>
            </div>
          );
        })}
      </div>

      <div className="section-heading">
        <div>
          <h2>Recent Projects</h2>
          <p>Your recently uploaded projects</p>
        </div>
      </div>

      {projects.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            <FolderOpen size={32} />
          </div>
          <h3>No projects yet</h3>
          <p>Upload your first Python project to get started.</p>
          <button className="primary-button" onClick={onUpload}>
            <Upload size={18} />
            Upload Your First Project
          </button>
        </div>
      ) : (
        <div className="projects-list">
          {projects.map((project) => (
            <div className="project-card" key={project.id}>
              <div className="project-info">
                <div className="project-icon">
                  <FileCode2 size={22} />
                </div>
                <div>
                  <h3>{project.project_name}</h3>
                  <p>
                    {project.python_file_count || 0} Python files
                    {" · "}
                    {project.filename}
                  </p>
                </div>
              </div>

              <div className="project-right">
                <span className="project-status">
                  {project.status || "uploaded"}
                </span>
                <button
                  className="icon-button"
                  onClick={() => onOpenProject(project)}
                  aria-label={`Open ${project.project_name}`}
                >
                  <ArrowUpRight size={20} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
