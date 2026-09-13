
export default function ReportPanel({ report, mode }) {
  if (!report) {
    return (
      <div className="report-section">
        <h3>Migration Report</h3>
        <div className="report-placeholder">
          Run migration to generate full analysis report.
        </div>
      </div>
    );
  }
  const rawConfidence = report.confidence ?? 0;

const confidencePercent =
  rawConfidence <= 1
    ? Math.round(rawConfidence * 100)   // decimal case (0.78 → 78)
    : Math.round(rawConfidence);        // already percentage (78 → 78)
  const riskClass =
    report.riskLevel === "HIGH"
      ? "risk-high"
      : report.riskLevel === "MEDIUM"
      ? "risk-medium"
      : "risk-low";

  const compileClass =
    report.compileSuccess === null
      ? ""
      : report.compileSuccess
      ? "compile-success"
      : "compile-failed";

  const accuracy = report?.accuracy ?? 0;

  return (
    <div className={`report-section ${mode}`}>
      <h3>Migration Intelligence Report</h3>

      {/* ===== Main Stats Grid ===== */}
      <div className="report-grid">

        {/* Accuracy */}
        <div className="report-box">
          <h4>Transformation Accuracy</h4>
          <div className="accuracy-value">{accuracy}%</div>
          <div className="accuracy-bar">
            <div
              className="accuracy-fill"
              style={{ width: `${accuracy}%` }}
            />
          </div>
          <p className="report-description">
            Measures structural similarity after migration based on diff changes.
          </p>
        </div>

        {/* Confidence */}
        <div className="report-box">
          <h4>Model Confidence</h4>
          <div
            className="confidence-circle"
            style={{ "--confidence": confidencePercent }}
            >
            <span>{confidencePercent}%</span>
          </div>
          <p className="report-description">
            AI-driven reliability score for the generated code.
          </p>
        </div>

        {/* Risk */}
        <div className="report-box">
          <h4>Risk Assessment</h4>
          <span className={`risk-badge ${riskClass}`}>
            {report.riskLevel}
          </span>
          <div className="risk-score">
            Risk Score: {report.riskScore}
          </div>
          <p className="report-description">
            Indicates potential breaking changes or unsafe transformations.
          </p>
        </div>

        {/* Compilation */}
        {report.compileSuccess !== null && (
          <div className="report-box">
            <h4>Compilation Status</h4>
            <span className={`compile-badge ${compileClass}`}>
              {report.compileSuccess
                ? "Compile Success"
                : "Compile Failed"}
            </span>
            {report.validationStatus && (
              <div className="validation-text">
                Validation: {report.validationStatus}
              </div>
            )}
            <p className="report-description">
              Verifies whether migrated code compiles successfully.
            </p>
          </div>
        )}

        {/* Version Detection */}
        {report.detectedVersion && (
          <div className="report-box">
            <h4>Detected Version</h4>
            <div className="version-text">
              {report.detectedVersion}
            </div>
            <p className="report-description">
              Original code version identified before upgrade.
            </p>
          </div>
        )}

        {/* Engine */}
        <div className="report-box">
          <h4>Migration Engine</h4>
          <div className="engine-text">
            {report.engine}
          </div>
          <p className="report-description">
            Engine responsible for performing transformation.
          </p>
        </div>
        {/* Time Taken */}
        {report.timeTakenMs && (
          <div className="report-box">
            <h4>Execution Time</h4>
            <div className="time-value">
              {report.timeTakenMs} ms
            </div>
            <p className="report-description">
              Total engine processing time.
            </p>
          </div>
        )}
        {/* ===== Upgrade Summary (Only for Version Mode) ===== */}
        {/* {mode === "upgrade" && (
          <div className="report-box upgrade-box">
            <h4>Upgrade Summary</h4>

            <div className="upgrade-stat">
              <strong>{report.totalDiffChanges}</strong>
              <span>Code Changes Applied</span>
            </div>

            <div className="upgrade-stat">
              <strong>{report.riskScore}</strong>
              <span>Modernization Impact Score</span>
            </div>

            {report.detectedVersion && (
              <div className="upgrade-version">
                From: {report.detectedVersion}
              </div>
            )}

            <p className="report-description">
              This upgrade modernizes deprecated constructs and improves
              compatibility with newer standards.
            </p>
          </div>
        )} */}
        {mode === "upgrade" && (
          <div className="report-box upgrade-box-premium">
            <h4>Upgrade Intelligence</h4>

            <div className="upgrade-grid">

              <div className="upgrade-metric">
                <div className="upgrade-number">
                  {report.totalDiffChanges}
                </div>
                <span>Code Changes Applied</span>
              </div>

              <div className="upgrade-metric">
                <div className="upgrade-number impact">
                  {report.riskScore}
                </div>
                <span>Modernization Impact</span>
              </div>

            </div>

            {report.detectedVersion && (
              <div className="upgrade-from">
                Upgraded From <strong>{report.detectedVersion}</strong>
              </div>
            )}

            <p className="report-description">
              Deprecated constructs were replaced and compatibility
              with modern standards has been improved.
            </p>
          </div>
        )}
        {/* Test Execution */}
        {report.testResults && (
          <div className="report-box">
            <h4>Test Execution Summary</h4>
            <div className="test-summary">
              {report.testResults.passed} / {report.testResults.total}
            </div>
            <div className="test-details">
              Failed: {report.testResults.failed}
            </div>
            <p className="report-description">
              Validates functional correctness using provided test cases.
            </p>
          </div>
        )}
      </div>

      {/* ===== Risk Triggers ===== */}
      {report.riskTriggers && report.riskTriggers.length > 0 && (
        <div className="risk-section">
          <h4>Triggered Risk Factors</h4>
          <div className="trigger-list">
            {report.riskTriggers.map((trigger, index) => (
              <div key={index} className="trigger-pill">
                {trigger}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ===== Semantic Issues ===== */}
      {report.semanticIssues &&
        report.semanticIssues.length > 0 && (
          <div className="semantic-block">
            <div className="semantic-title">
              <div className="semantic-icon">⚠</div>
              Semantic Analysis Findings
            </div>

            <ul className="semantic-list">
              {report.semanticIssues.map((issue, index) => (
                <li key={index}>{issue}</li>
              ))}
            </ul>
          </div>
        )}
    </div>
  );
}