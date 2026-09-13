import { Navigate } from "react-router-dom";
import { useMigration } from "../context/MigrationContext";

export default function ProtectedRoute({ children }) {
  const { migrationConfig } = useMigration();

  if (!migrationConfig) {
    return <Navigate to="/" replace />;
  }

  return children;
}