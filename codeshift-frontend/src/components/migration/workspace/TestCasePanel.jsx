export default function TestCasePanel({
  value,
  onChange
}) {
  return (
    <div className="test-section">

      <h3>Test Cases (Optional)</h3>

      <p className="test-hint">
        Separate cases with <code>---</code>. Put expected output after{" "}
        <code>===</code>. Without it, the migrated program is compared against
        the original.
      </p>

      <textarea
        className="test-area"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={"2 3\n===\n5\n---\n10 20\n===\n30"}
      />

    </div>
  );
}