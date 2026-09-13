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