export default function TestResultsCard({ passed, total }) {
  return (
    <div className="report-box">

      <h4>Test Results</h4>

      <div className="test-summary">
        {total !== null
          ? `${passed} / ${total} Passed`
          : "--"}
      </div>

    </div>
  );
}