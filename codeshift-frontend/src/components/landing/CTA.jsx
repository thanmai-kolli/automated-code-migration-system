
import { useNavigate } from "react-router-dom";

export default function CTA() {
  const navigate = useNavigate();

  return (
    <section className="cta-section">

      <div className="cta-glow"></div>

      <div className="cta-container">
        <h2>
          Ready to Transform Your{" "}
          <span className="highlight">Codebase?</span>
        </h2>

        <p>
          Migrate across languages or upgrade legacy versions
          with intelligent automation and confidence scoring.
        </p>

        <button
          className="cta-button"
          onClick={() => navigate("/migration")}
        >
          Start Migrating →
        </button>
      </div>

    </section>
  );
}