

export default function Features() {
  return (
    <section className="features-section">

      <div className="features-header">
        <h2>
          Everything You Need for{" "}
          <span className="highlight">Code Migration</span>
        </h2>
        <p>
          A complete toolkit for converting, upgrading, and validating
          your code across languages and versions.
        </p>
      </div>

      <div className="features-grid">

        <FeatureCard
        //   icon="↔"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
             <path d="M8 7l-5 5 5 5" />
            <path d="M16 7l5 5-5 5" />
            </svg>  
            }
          title="Cross-Language Conversion"
          text="Seamlessly convert code between Java, Python, C, and C++ with AST-aware transformations that preserve logic and structure."
        />

        <FeatureCard
        //   icon="⇅"
        icon={
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 3v18" />
                <path d="M7 8l5-5 5 5" />
            </svg>
        }
          title="Version Upgrades"
          text="Upgrade legacy codebases to modern language versions. From Python 2 to 3, Java 8 to 21, and beyond."
        />

        <FeatureCard
        //   icon="{}"
        icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="8" y="14" width="8" height="7" />
        </svg>
        }
          title="AST Parsing Engine"
          text="Deep Abstract Syntax Tree analysis ensures structural accuracy, handling complex patterns like generics, lambdas, and templates."
        />

        <FeatureCard
        //   icon="⚡"
            icon = { <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19 12h2M3 12h2M12 3v2M12 19v2" />
            <path d="M17 17l1.5 1.5M5.5 5.5L7 7M17 7l1.5-1.5M5.5 18.5L7 17" />
            </svg>
            }
          title="ML-Powered Intelligence"
          text="Machine learning models trained on millions of code patterns to produce idiomatic, clean output in your target language."
        />

        <FeatureCard
        //   icon="✓"
        icon = {<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 12l2 2 4-4" />
            <rect x="3" y="3" width="18" height="18" rx="2" />
            </svg>  }
          title="Test Case Validation"
          text="Add custom test cases and verify that converted code produces identical outputs. Confidence through automated testing."
        />

        <FeatureCard
        //   icon="⌘"
        icon = {<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 20h16" />
            <path d="M6 16V4h12v12" />
            <path d="M9 9h6M9 12h6" />
            </svg>}
          title="Interactive Editor"
          text="Edit, refine, and copy converted code with a full-featured code editor with syntax highlighting."
        />

      </div>

    </section>
  );
}

function FeatureCard({ icon, title, text }) {
  return (
    <div className="feature-card">
      <div className="feature-icon-box">
        {icon}
      </div>
      <div className="feature-content">
        <h3>{title}</h3>
        <p>{text}</p>
      </div>
    </div>
  );
}