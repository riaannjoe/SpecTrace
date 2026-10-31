
import {
  CheckCircle2,
  AlertCircle,
  Clock,
  ShieldCheck,
  FileCode2,
} from "lucide-react";

export default function Results({ results, onBack }) {
  if (!results) {
    return (
      <div className="page-content">
        <h2>No analysis results available</h2>
        <button className="secondary-button" onClick={onBack}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  const summary = results.summary || {};
  const items = results.results || [];

  const statusInfo = {
    implemented: {
      label: "Implemented",
      icon: CheckCircle2,
      className: "status-implemented",
    },
    partially_implemented: {
      label: "Partially Implemented",
      icon: Clock,
      className: "status-partial",
    },
    missing: {
      label: "Missing",
      icon: AlertCircle,
      className: "status-missing",
    },
    not_verified: {
      label: "Not Verified",
      icon: ShieldCheck,
      className: "status-unverified",
    },
  };

  return (
    <div className="page-content">
      <div className="welcome-section">
        <div>
          <h2>Analysis Results</h2>
          <p>
            Requirement analysis for {results.project_name}
          </p>
        </div>

        <button className="secondary-button" onClick={onBack}>
          Back to Dashboard
        </button>
      </div>

      {results.is_mock && (
        <div className="demo-banner">
          <AlertCircle size={20} />
          <div>
            <strong>Demo data — real analysis engine not connected</strong>
            <p>
              These results are not verified by an actual code analysis engine.
            </p>
          </div>
        </div>
      )}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon"><FileCode2 size={22} /></div>
          <p>Total Requirements</p>
          <h2>{summary.total ?? 0}</h2>
        </div>

        <div className="stat-card">
          <div className="stat-icon"><CheckCircle2 size={22} /></div>
          <p>Implemented</p>
          <h2>{summary.implemented ?? 0}</h2>
        </div>

        <div className="stat-card">
          <div className="stat-icon"><Clock size={22} /></div>
          <p>Partially Implemented</p>
          <h2>{summary.partially_implemented ?? 0}</h2>
        </div>

        <div className="stat-card">
          <div className="stat-icon"><AlertCircle size={22} /></div>
          <p>Missing</p>
          <h2>{summary.missing ?? 0}</h2>
        </div>
      </div>

      <div className="section-heading">
        <div>
          <h2>Requirement Breakdown</h2>
          <p>Individual status and evidence for each requirement</p>
        </div>
      </div>

      <div className="results-list">
        {items.length === 0 ? (
          <p>No individual results returned by the server.</p>
        ) : (
          items.map((item, index) => {
            const status =
              statusInfo[item.status] || statusInfo.not_verified;
            const Icon = status.icon;

            return (
              <div className="result-card" key={index}>
                <div className="result-top">
                  <span className="requirement-number">{index + 1}</span>
                  <span className={`result-status ${status.className}`}>
                    <Icon size={15} />
                    {status.label}
                  </span>
                </div>

                <h3>{item.requirement}</h3>

                <p>{item.explanation || "No explanation provided."}</p>

                {item.evidence && (
                  <div className="evidence-box">
                    <strong>Evidence</strong>
                    {Array.isArray(item.evidence) ? (
                      item.evidence.map((evidence, i) => (
                        <p key={i}>
                          {evidence.file || "Unknown file"}
                          {evidence.line ? ` · Line ${evidence.line}` : ""}
                          {evidence.description
                            ? ` — ${evidence.description}`
                            : ""}
                        </p>
                      ))
                    ) : (
                      <p>
                        {item.evidence.file || "Unknown file"}
                        {item.evidence.line
                          ? ` · Line ${item.evidence.line}`
                          : ""}
                        {item.evidence.description
                          ? ` — ${item.evidence.description}`
                          : ""}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
