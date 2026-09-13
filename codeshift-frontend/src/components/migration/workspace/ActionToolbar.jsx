export default function ActionToolbar({
  onRun,
  loading
}) {
  return (
    <div className="workspace-toolbar">

      <button
        className={`btn-primary ${loading ? "loading" : ""}`}
        onClick={onRun}
        disabled={loading}
      >
        {loading ? <div className="loader"></div> : "Run Migration"}
      </button>

    </div>
  );
}