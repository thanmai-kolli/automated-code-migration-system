import { BrowserRouter } from "react-router-dom";
import AppRoutes from "./routes/AppRoutes";
import Navbar from "./components/layout/Navbar";
import { MigrationProvider } from "./context/MigrationContext";
import "./styles/global.css";
import "./styles/layout.css";
import "./styles/landing.css";
import "./styles/migration.css";
export default function App() {
  return (
    <BrowserRouter>
      <MigrationProvider>
        <Navbar />
        <AppRoutes />
      </MigrationProvider>
    </BrowserRouter>
  );
}