import { Bell, Search, Loader2 } from "lucide-react";

const LOADING_LABELS = {
  uploading: "Uploading project…",
  saving: "Saving requirements…",
  analyzing: "Running analysis — this may take a moment…",
};

export default function Navbar({ title, loadingState = "idle" }) {
  const label = LOADING_LABELS[loadingState];

  return (
    <header className="navbar">
      <div>
        <h1>{title || "Dashboard"}</h1>
        {label ? (
          <p className="navbar-loading">
            <Loader2 size={13} className="spin" />
            {label}
          </p>
        ) : (
          <p>Welcome to SpecTrace</p>
        )}
      </div>

      <div className="navbar-actions">
        <div className="navbar-search">
          <Search size={17} />
          <input type="text" placeholder="Search projects…" />
        </div>

        <button className="notification-button" aria-label="Notifications">
          <Bell size={20} />
        </button>
      </div>
    </header>
  );
}
