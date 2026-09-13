// import ModeCard from "../components/migration/ModeCard";
// import "../styles/migration.css";

// export default function MigrationType() {
//   return (
//     <div className="migration-type-page">

//       <div className="migration-type-header">
//         <h1>Select <span className="highlight">Migration Mode</span></h1>
//         <p>Choose how you want to transform your codebase.</p>
//       </div>

//       <div className="migration-type-grid">

//         <ModeCard
//           mode="cross"
//           icon={
//             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
//               <path d="M8 7l-5 5 5 5" />
//               <path d="M16 7l5 5-5 5" />
//             </svg>
//           }
//           title="Cross-Language Conversion"
//           description="Convert between Java, Python, C, and C++ with structure-aware transformation."
//         />

//         <ModeCard
//           mode="upgrade"
//           icon={
//             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
//               <path d="M12 3v18" />
//               <path d="M7 8l5-5 5 5" />
//             </svg>
//           }
//           title="Version Upgrade"
//           description="Upgrade legacy codebases to modern language versions."
//         />

//       </div>
//     </div>
//   );
// }
import { useState } from "react";
import ModeStep from "../components/migration/steps/ModeStep";
import ConfigurationStep from "../components/migration/steps/ConfigurationStep";
import WorkspaceStep from "../components/migration/steps/WorkspaceStep";
import "../styles/migration.css";

export default function Migration() {
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState(null);
  const [config, setConfig] = useState({});
  const [animateKey, setAnimateKey] = useState(0);

  const changeStep = (nextStep) => {
    setAnimateKey(prev => prev + 1);
    setStep(nextStep);
  };

  return (
    <div className="migration-page">

      {/* Step Indicator */}
      <div className="step-indicator">
        <div className={step >= 1 ? "active" : ""}>1</div>
        <div className={step >= 2 ? "active" : ""}>2</div>
        <div className={step >= 3 ? "active" : ""}>3</div>
      </div>

      <div key={animateKey} className="step-content">

        {step === 1 && (
          <ModeStep
            onSelect={(selectedMode) => {
              setMode(selectedMode);
              changeStep(2);
            }}
          />
        )}

        {step === 2 && (
          <ConfigurationStep
            mode={mode}
            onBack={() => changeStep(1)}
            onContinue={(data) => {
              setConfig(data);
              changeStep(3);
            }}
          />
        )}

        {step === 3 && (
          <WorkspaceStep
            mode={mode}
            config={config}
            onBack={() => changeStep(2)}
          />
        )}

      </div>

    </div>
  );
}