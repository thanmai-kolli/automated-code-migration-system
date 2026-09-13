export default function WorkspaceHeader({ mode, config, onBack }) {
  return (
    <div className="workspace-header">
      <h2>
        {mode === "cross"
          ? `${config.sourceLang} → ${config.targetLang}`
          : `${config.sourceLang} Version Upgrade`}
      </h2>

      <button className="nav-back-btn" onClick={onBack}>
        ← Back
      </button>
    </div>
  );
}