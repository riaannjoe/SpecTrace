
import {
  Code2,
  LayoutDashboard,
  Upload,
  FolderOpen,
  ShieldCheck,
} from "lucide-react";

export default function Sidebar({ activePage, setActivePage }) {
  const menuItems = [
    { name: "Dashboard", icon: LayoutDashboard },
    { name: "Upload Project", icon: Upload },
    { name: "Projects", icon: FolderOpen },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">
          <ShieldCheck size={24} />
        </div>
        <div>
          <h2>SpecTrace</h2>
          <p>Requirement Analyzer</p>
        </div>
      </div>

      <p className="sidebar-heading">MENU</p>

      <nav className="sidebar-menu">
        {menuItems.map((item) => {
          const Icon = item.icon;

          return (
            <button
              key={item.name}
              className={`sidebar-link ${
                activePage === item.name ? "active" : ""
              }`}
              onClick={() => setActivePage(item.name)}
            >
              <Icon size={19} />
              <span>{item.name}</span>
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <Code2 size={16} />
        <span>SpecTrace v1.0</span>
      </div>
    </aside>
  );
}
