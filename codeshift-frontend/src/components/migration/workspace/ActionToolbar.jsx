export default function ActionToolbar({
  onRun,
  onCopy,
  onDownload,
  copied,
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

      {/* <button className="btn-secondary" onClick={onCopy}>
        {copied ? "Copied ✓" : "Copy Output"}
      </button> */}

    </div>
  );
}