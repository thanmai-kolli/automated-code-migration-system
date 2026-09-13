export default function ConfidenceMeter({ confidence }) {
  const percentage =
    confidence !== null && confidence !== undefined
      ? Math.round(confidence * 100)
      : 0;

  return (
    <div className="report-box">

      <h4>Model Confidence</h4>

      <div
        className="confidence-circle"
        style={{ "--confidence": percentage }}
      >
        <span>
          {confidence !== null ? `${percentage}%` : "--"}
        </span>
      </div>

      <p className="report-description">
        AI-driven reliability score for the generated code.
      </p>

    </div>
  );
}