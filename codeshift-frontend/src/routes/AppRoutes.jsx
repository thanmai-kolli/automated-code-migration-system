import { Routes, Route } from "react-router-dom";
import Landing from "../pages/Landing";
import Migration from "../pages/Migration";
// import ProtectedRoute from "./ProtectedRoute";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/migration" element={<Migration />} />
    </Routes>
  );
}