export default function AccuracyCard({ accuracy }) {
  return (
    <div className="report-box">

      <h4>Accuracy</h4>

      <div className="accuracy-value">
        {accuracy !== null ? `${accuracy}%` : "--"}
      </div>

      <div className="accuracy-bar">
        <div
          className="accuracy-fill"
          style={{ width: accuracy ? `${accuracy}%` : "0%" }}
        />
      </div>

    </div>
  );
}