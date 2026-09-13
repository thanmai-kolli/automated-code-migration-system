// import { useNavigate } from "react-router-dom";
// import "./layout.css";

// export default function Navbar() {
//   const navigate = useNavigate();

//   return (
//     <nav className="navbar">
//       <div className="logo"
//         onClick={() => navigate("/")}
//         style={{ cursor: "pointer" }}>
//         <span style={{ color: "#00e5ff" }}>{"</>"}</span>
//         <span style={{ marginLeft: "6px", color: "white" }}>
//           CodeShift
//         </span>
//       </div>

//       <button
//         className="start-btn"
//         onClick={() => navigate("/type-selection")}
//       >
//         Start Migrating →
//       </button>
//     </nav>
//   );
// }
import { useNavigate, useLocation } from "react-router-dom";


export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();

  const isMigrationPage =
    location.pathname.startsWith("/migration")

  return (
    <nav className={`navbar ${isMigrationPage ? "navbar-migration" : ""}`}>

      {/* Logo */}
      <div
        className="logo"
        onClick={() => navigate("/")}
        style={{ cursor: "pointer" }}
      >
        <span style={{ color: "#00e5ff" }}>{"</>"}</span>
        <span style={{ marginLeft: "6px", color: "white" }}>
          CodeShift
        </span>
      </div>

      {/* Right Side */}
      {isMigrationPage ? (
        <button
          className="nav-back-btn"
          onClick={() => navigate("/")}
        >
          ← Back to Home
        </button>
      ) : (
        <button
          className="start-btn"
          onClick={() => navigate("/migration")}
        >
          Start Migrating →
        </button>
      )}

    </nav>
  );
}