import { BrowserRouter } from "react-router-dom";
import { Toaster } from "react-hot-toast";
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
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: { background: "#0d1b26", color: "#d6dde3", border: "1px solid #1d3547" },
          }}
        />
      </MigrationProvider>
    </BrowserRouter>
  );
}