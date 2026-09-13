import ModeCard from "../ModeCard";
import "../../../styles/migration.css";

export default function ModeStep({ onSelect }) {
  return (
    <div className="migration-type-page">

      <div className="migration-type-header">
        <h1>
          Select <span className="highlight">Migration Mode</span>
        </h1>
        <p>Choose how you want to transform your codebase.</p>
      </div>

      <div className="migration-type-grid">

        <ModeCard
          mode="cross"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 7l-5 5 5 5" />
              <path d="M16 7l5 5-5 5" />
            </svg>
          }
          title="Cross-Language Conversion"
          description="Convert between Java, Python, C, and C++ with structure-aware transformation."
          onSelect={onSelect}
        />

        <ModeCard
          mode="upgrade"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 3v18" />
              <path d="M7 8l5-5 5 5" />
            </svg>
          }
          title="Version Upgrade"
          description="Upgrade legacy codebases to modern language versions."
          onSelect={onSelect}
        />

      </div>
    </div>
  );
}