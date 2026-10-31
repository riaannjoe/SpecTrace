
import { Bell, Search } from "lucide-react";

export default function Navbar({ title }) {
  return (
    <header className="navbar">
      <div>
        <h1>{title || "Dashboard"}</h1>
        <p>Welcome to SpecTrace</p>
      </div>

      <div className="navbar-actions">
        <div className="navbar-search">
          <Search size={17} />
          <input type="text" placeholder="Search projects..." />
        </div>

        <button className="notification-button" aria-label="Notifications">
          <Bell size={20} />
        </button>
      </div>
    </header>
  );
}
