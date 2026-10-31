import {
  CheckCircle2,
  AlertCircle,
  Clock,
  ShieldCheck,
  FileCode2,
  BarChart2,
  FlaskConical,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Loader2,
} from "lucide-react";
import { useState } from "react";

// ─── Status metadata ──────────────────────────────────────────────────────────

const STATUS_INFO = {
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

const RISK_LABELS = {
  critical: { label: "Critical Risk", className: "risk-critical" },
  high: { label: "High Risk", className: "risk-high" },
  medium: { label: "Medium Risk", className: "risk-medium" },
  low: { label: "Low Risk", className: "risk-low" },
};

// ─── Evidence block ────────────────────────────────────────────────────────────

function EvidenceItem({ ev }) {
  return (
    <div className="evidence-item">
      <div className="evidence-file">
        <FileCode2 size={13} />
        <span>{ev.file}</span>
        {ev.line != null && (
          <span className="evidence-line">
            L{ev.line}
            {ev.line_end != null && ev.line_end !== ev.line
              ? `–${ev.line_end}`
              : ""}
          </span>
        )}
        {ev.function && (
          <span className="evidence-fn">{ev.function}()</span>
        )}
      </div>
      {ev.description && (
        <p className="evidence-desc">{ev.description}</p>
      )}
      {ev.snippet && (
        <pre className="evidence-snippet"><code>{ev.snippet}</code></pre>
      )}
    </div>
  );
}

// ─── Individual result card ───────────────────────────────────────────────────

function ResultCard({ item, index }) {
  const [expanded, setExpanded] = useState(false);

  const statusMeta = STATUS_INFO[item.status] ?? STATUS_INFO.not_verified;
  const StatusIcon = statusMeta.icon;
  const riskMeta = item.risk ? RISK_LABELS[item.risk] : null;

  const hasEvidence = item.evidence && item.evidence.length > 0;
  const hasTestEvidence = item.test_evidence && item.test_evidence.length > 0;

  // `test_status` is always "not_run" for static analysis — never display as "passed".
  const testStatusLabel =
    item.test_status === "not_run"
      ? "Tests not run (static discovery only)"
      : item.test_status === "passed"
        ? "Tests passed"
        : item.test_status === "failed"
          ? "Tests failed"
          : null;

  return (
    <div className="result-card">
      {/* ── Header ── */}
      <div className="result-top">
        <div className="result-top-left">
          <span className="requirement-number">{index + 1}</span>
          <span className={`result-status ${statusMeta.className}`}>
            <StatusIcon size={13} />
            {statusMeta.label}
          </span>
          {riskMeta && (
            <span className={`result-risk ${riskMeta.className}`}>
              {riskMeta.label}
            </span>
          )}
        </div>

        <button
          className="icon-button"
          onClick={() => setExpanded((e) => !e)}
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* ── Requirement text ── */}
      {/* Backend field: requirement_description */}
      <h3>{item.requirement_description || "—"}</h3>

      {/* ── Requirement ID ── */}
      <p className="result-req-id">ID: {item.requirement_id}</p>

      {/* ── Explanation ── */}
      <p className="result-explanation">
        {item.explanation || "No explanation provided."}
      </p>

      {/* ── Confidence & mode badges ── */}
      <div className="result-badges">
        {item.confidence != null && (
          <span className="badge badge-confidence">
            Confidence: {(item.confidence * 100).toFixed(0)}%
          </span>
        )}
        {item.analysis_mode && (
          <span className="badge badge-mode">{item.analysis_mode.replace("_", " ")}</span>
        )}
        {item.test_covered === true && (
          <span className="badge badge-test">Test candidate found</span>
        )}
      </div>

      {/* ── Risk reason ── */}
      {item.risk_reason && (
        <p className="result-risk-reason">
          <strong>Risk reason:</strong> {item.risk_reason}
        </p>
      )}

      {/* ── Expanded detail section ── */}
      {expanded && (
        <div className="result-detail">
          {/* Evidence */}
          {hasEvidence ? (
            <div className="evidence-box">
              <strong>
                <FileCode2 size={13} /> Implementation Evidence
              </strong>
              {item.evidence.map((ev, i) => (
                <EvidenceItem key={i} ev={ev} />
              ))}
            </div>
          ) : (
            <div className="evidence-box evidence-empty">
              No implementation evidence found.
            </div>
          )}

          {/* Test evidence */}
          {hasTestEvidence && (
            <div className="evidence-box evidence-test">
              <strong>
                <FlaskConical size={13} /> Test Evidence
              </strong>
              {item.test_evidence.map((ev, i) => (
                <EvidenceItem key={i} ev={ev} />
              ))}
            </div>
          )}

          {/* Test status note */}
          {testStatusLabel && (
            <p className="result-test-status">{testStatusLabel}</p>
          )}

          {/* Engine info */}
          {item.engine && (
            <p className="result-engine">Engine: {item.engine}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Summary bar ─────────────────────────────────────────────────────────────

function SummaryStats({ summary }) {
  const cards = [
    { label: "Total", value: summary.total ?? 0, icon: BarChart2 },
    { label: "Implemented", value: summary.implemented ?? 0, icon: CheckCircle2 },
    { label: "Partial", value: summary.partially_implemented ?? 0, icon: Clock },
    { label: "Missing", value: summary.missing ?? 0, icon: AlertCircle },
    { label: "Not Verified", value: summary.not_verified ?? 0, icon: ShieldCheck },
  ];

  const riskCards = [
    { label: "Critical", value: summary.critical_risks ?? 0, className: "risk-critical" },
    { label: "High", value: summary.high_risks ?? 0, className: "risk-high" },
    { label: "Medium", value: summary.medium_risks ?? 0, className: "risk-medium" },
    { label: "Low", value: summary.low_risks ?? 0, className: "risk-low" },
  ].filter((r) => r.value > 0);

  return (
    <>
      <div className="stats-grid stats-grid-5">
        {cards.map((c) => {
          const Icon = c.icon;
          return (
            <div className="stat-card" key={c.label}>
              <div className="stat-icon">
                <Icon size={20} />
              </div>
              <p>{c.label}</p>
              <h2>{c.value}</h2>
            </div>
          );
        })}
      </div>

      {riskCards.length > 0 && (
        <div className="risk-summary">
          <span className="risk-summary-label">Risk counts (verified only):</span>
          {riskCards.map((r) => (
            <span key={r.label} className={`risk-badge ${r.className}`}>
              {r.label}: {r.value}
            </span>
          ))}
        </div>
      )}
    </>
  );
}

// ─── Results page ─────────────────────────────────────────────────────────────

export default function Results({
  results,
  project,
  onBack,
  onReanalyze,
  loading,
  loadingState,
}) {
  if (!results) {
    return (
      <div className="page-content">
        <h2>No analysis results available</h2>
        <p style={{ color: "#8f98ad", marginTop: 8, marginBottom: 20 }}>
          Upload a project and run analysis to see results here.
        </p>
        <button className="secondary-button" onClick={onBack}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  const summary = results.summary ?? {};
  const items = results.results ?? [];

  const isMock = results.is_mock === true;
  const analysisMode = results.analysis_mode;

  return (
    <div className="page-content">
      {/* ── Page header ── */}
      <div className="welcome-section">
        <div>
          <h2>Analysis Results</h2>
          <p>
            {results.project_name
              ? `Results for "${results.project_name}"`
              : project?.project_name
                ? `Results for "${project.project_name}"`
                : "Requirement analysis complete"}
          </p>
        </div>

        <div className="results-header-actions">
          {onReanalyze && (
            <button
              className="secondary-button"
              onClick={onReanalyze}
              disabled={loading}
            >
              {loadingState === "analyzing" ? (
                <Loader2 size={15} className="spin" />
              ) : (
                <RefreshCw size={15} />
              )}
              {loadingState === "analyzing" ? "Analyzing…" : "Re-run Analysis"}
            </button>
          )}
          <button className="secondary-button" onClick={onBack}>
            Back to Dashboard
          </button>
        </div>
      </div>

      {/* ── Mock warning ── */}
      {isMock && (
        <div className="demo-banner">
          <AlertCircle size={20} />
          <div>
            <strong>Demo data — real analysis engine not connected</strong>
            <p>
              These results are placeholder output. Set{" "}
              <code>ANALYSIS_ENGINE=real</code> in the backend <code>.env</code>{" "}
              to run actual code analysis.
            </p>
          </div>
        </div>
      )}

      {/* ── Analysis mode note ── */}
      {!isMock && analysisMode === "static_fallback" && (
        <div className="demo-banner" style={{ borderColor: "#4a6280", color: "#a8c8e8" }}>
          <ShieldCheck size={20} />
          <div>
            <strong>Static analysis mode</strong>
            <p>
              Gemini API is not configured or unavailable. Results are from
              static code analysis only.
            </p>
          </div>
        </div>
      )}

      {/* ── Summary stats ── */}
      <SummaryStats summary={summary} />

      {/* ── Result list ── */}
      <div className="section-heading">
        <div>
          <h2>Requirement Breakdown</h2>
          <p>Individual status and evidence for each requirement</p>
        </div>
        {summary.tests_covered > 0 && (
          <span className="badge badge-test">
            <FlaskConical size={13} />
            {summary.tests_covered} test candidate
            {summary.tests_covered !== 1 ? "s" : ""} found
          </span>
        )}
      </div>

      <div className="results-list">
        {items.length === 0 ? (
          <div className="empty-state">
            <p>No individual results returned by the server.</p>
          </div>
        ) : (
          items.map((item, index) => (
            <ResultCard key={item.id ?? index} item={item} index={index} />
          ))
        )}
      </div>
    </div>
  );
}
