export default function TestCasePanel({
  value,
  onChange
}) {
  return (
    <div className="test-section">

      <h3>Test Cases (Optional)</h3>

      <textarea
        className="test-area"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Add test cases to validate migration..."
      />

    </div>
  );
}