import { useState } from "react";
import { FileText, Plus, Trash2, ArrowRight, Loader2 } from "lucide-react";

export default function Requirements({ project, onSubmit, loading, loadingState }) {
  const [requirements, setRequirements] = useState([""]);

  function updateRequirement(index, value) {
    setRequirements((prev) => prev.map((item, i) => (i === index ? value : item)));
  }

  function addRequirement() {
    setRequirements((prev) => [...prev, ""]);
  }

  function removeRequirement(index) {
    setRequirements((prev) => prev.filter((_, i) => i !== index));
  }

  function handleSubmit(event) {
    event.preventDefault();

    const valid = requirements.map((r) => r.trim()).filter(Boolean);

    if (valid.length === 0) {
      alert("Please enter at least one requirement.");
      return;
    }

    onSubmit(valid);
  }

  let buttonLabel = "Save & Analyze";
  if (loadingState === "saving") buttonLabel = "Saving requirements…";
  else if (loadingState === "analyzing") buttonLabel = "Analyzing…";
  else if (loading) buttonLabel = "Working…";

  return (
    <div className="page-content">
      <div className="welcome-section">
        <div>
          <h2>Define Requirements</h2>
          <p>Specify what your uploaded project is expected to do.</p>
        </div>
      </div>

      <div className="requirement-project-card">
        <FileText size={22} />
        <div>
          <strong>{project?.project_name || "Your Project"}</strong>
          <p>Enter one requirement in each field. Analysis will run automatically after saving.</p>
        </div>
      </div>

      <form className="requirements-card" onSubmit={handleSubmit}>
        <div className="section-heading">
          <div>
            <h2>Project Requirements</h2>
            <p>Be clear and specific about each requirement.</p>
          </div>
        </div>

        {requirements.map((requirement, index) => (
          <div className="requirement-input-row" key={index}>
            <span className="requirement-number">{index + 1}</span>
            <input
              type="text"
              placeholder={`Requirement ${index + 1}, e.g. The system should allow user login`}
              value={requirement}
              onChange={(e) => updateRequirement(index, e.target.value)}
            />
            {requirements.length > 1 && (
              <button
                type="button"
                className="icon-button"
                onClick={() => removeRequirement(index)}
                aria-label="Remove requirement"
              >
                <Trash2 size={18} />
              </button>
            )}
          </div>
        ))}

        <button
          type="button"
          className="secondary-button"
          onClick={addRequirement}
          disabled={loading}
        >
          <Plus size={18} />
          Add Another Requirement
        </button>

        <button type="submit" className="primary-button" disabled={loading}>
          {loading && <Loader2 size={16} className="spin" />}
          {buttonLabel}
          {!loading && <ArrowRight size={18} />}
        </button>
      </form>
    </div>
  );
}
