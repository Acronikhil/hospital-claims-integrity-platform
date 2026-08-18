import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";
import UploadClaim from "./pages/UploadClaim.jsx";
import ClaimDetail from "./pages/ClaimDetail.jsx";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">◆</span>
          <span>Claims Integrity Platform</span>
        </div>
        <nav className="app-nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            Dashboard
          </NavLink>
          <NavLink to="/upload" className={({ isActive }) => (isActive ? "active" : "")}>
            Upload Claim
          </NavLink>
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<UploadClaim />} />
          <Route path="/claims/:claimId" element={<ClaimDetail />} />
        </Routes>
      </main>
    </div>
  );
}
