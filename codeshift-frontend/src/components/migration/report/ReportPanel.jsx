
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
  const rawConfidence = report.confidence;
  const confidencePercent =
    rawConfidence === null
      ? null
      : rawConfidence <= 1
      ? Math.round(rawConfidence * 100)
      : Math.round(rawConfidence);

  const riskClass =
    report.riskLevel === "HIGH"
      ? "risk-high"
      : report.riskLevel === "LOW"
      ? "risk-low"
      : "risk-medium";

  const compileClass =
    report.compileSuccess === null
      ? ""
      : report.compileSuccess
      ? "compile-success"
      : "compile-failed";

  // A measured test pass rate always beats the model's prediction.
  const tests = report.testResults;
  const measured = tests && tests.enabled !== false && tests.total > 0;
  const accuracy = measured
    ? Math.round((100 * tests.passed) / tests.total)
    : report.accuracy;

  return (
    <div className={`report-section ${mode}`}>
      <h3>Migration Intelligence Report</h3>

      {/* ===== Main Stats Grid ===== */}
      <div className="report-grid">

        {/* Accuracy */}
        <div className="report-box">
          <h4>{measured ? "Measured Accuracy" : "Predicted Accuracy"}</h4>
          {accuracy === null ? (
            <div className="accuracy-value">—</div>
          ) : (
            <>
              <div className="accuracy-value">{accuracy}%</div>
              <div className="accuracy-bar">
                <div
                  className="accuracy-fill"
                  style={{ width: `${accuracy}%` }}
                />
              </div>
            </>
          )}
          <p className="report-description">
            {measured
              ? "Share of your test cases on which the migrated program printed exactly what the original printed."
              : accuracy === null
              ? "Add test cases to measure behaviour."
              : "Model estimate of the share of inputs handled like the original. Add test cases for a measured value."}
          </p>
        </div>

        {/* Confidence */}
        {confidencePercent !== null && (
          <div className="report-box">
            <h4>Model Confidence</h4>
            <div
              className="confidence-circle"
              style={{ "--confidence": confidencePercent }}
            >
              <span>{confidencePercent}%</span>
            </div>
            <p className="report-description">
              Estimated probability that the migration preserves behaviour.
            </p>
          </div>
        )}

        {/* Risk */}
        <div className="report-box">
          <h4>Risk Assessment</h4>
          <span className={`risk-badge ${riskClass}`}>
            {report.riskLevel}
          </span>
          {report.riskScore !== null && (
            <div className="risk-score">
              Risk Score: {report.riskScore}
            </div>
          )}
          <p className="report-description">
            Based on compilation, unsupported constructs, risky rewrites and failed test cases.
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
        {mode === "upgrade" && (
          <div className="report-box upgrade-box-premium">
            <h4>Upgrade Intelligence</h4>

            <div className="upgrade-grid">

              <div className="upgrade-metric">
                <div className="upgrade-number">
                  {report.appliedRules.length}
                </div>
                <span>Rules Applied</span>
              </div>

              <div className="upgrade-metric">
                <div className="upgrade-number impact">
                  {report.rejectedRules.length}
                </div>
                <span>Rules Rejected by Validation</span>
              </div>

            </div>

            {report.detectedVersion && (
              <div className="upgrade-from">
                Upgraded From <strong>{report.detectedVersion}</strong>
              </div>
            )}

            <p className="report-description">
              {report.appliedRules.length === 0
                ? "No legacy construct could be rewritten safely; the code is unchanged."
                : "Each rule was kept only if the program still compiled (and passed your test cases, if given)."}
            </p>
          </div>
        )}
        {/* Test Execution */}
        {report.testResults && (
          <div className="report-box">
            <h4>Test Execution Summary</h4>

            {report.testResults.enabled === false ? (
              <>
                <div className="test-summary">Not run</div>
                <p className="report-description">{report.testResults.reason}</p>
              </>
            ) : (
              <>
                <div className="test-summary">
                  {report.testResults.passed} / {report.testResults.total}
                </div>
                <div className="test-details">
                  Failed: {report.testResults.failed}
                </div>

                {report.testResults.cases?.some((c) => !c.passed) && (
                  <ul className="test-failures">
                    {report.testResults.cases
                      .filter((c) => !c.passed)
                      .map((c) => (
                        <li key={c.index}>
                          <strong>Case {c.index}</strong>
                          {c.error
                            ? ` — ${c.error}`
                            : ` — expected ${JSON.stringify(
                                c.expected ?? c.source_output
                              )}, got ${JSON.stringify(c.target_output)}`}
                        </li>
                      ))}
                  </ul>
                )}

                <p className="report-description">
                  Runs both programs on your inputs and compares their output.
                </p>
              </>
            )}
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