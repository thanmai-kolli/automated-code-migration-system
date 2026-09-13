import Editor from "@monaco-editor/react";
import { useState } from "react";
import { fileExtension, monacoLanguage } from "../../../utils/language";

export default function OutputEditor({
  language,
  value
}) {

  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleEditorDidMount = (editor, monaco) => {

    monaco.editor.defineTheme("codeshift-dark", {
      base: "vs-dark",
      inherit: true,

      rules: [
        { token: "keyword", foreground: "00D9FF" },
        { token: "type", foreground: "00FFA3" },
        { token: "string", foreground: "FFB347" },
        { token: "number", foreground: "00FFA3" },
        { token: "comment", foreground: "5F6F82", fontStyle: "italic" },
        { token: "delimiter", foreground: "9BDcff" },
        { token: "operator", foreground: "00D9FF" },
        { token: "identifier", foreground: "D6DDE3" }
      ],

      colors: {
        "editor.background": "#061724",
        "editorLineNumber.foreground": "#3f5668",
        "editorCursor.foreground": "#00d9ff",
        "editor.lineHighlightBackground": "#072033",
        "editor.selectionBackground": "#003f5c55"
      }
    });

    monaco.editor.setTheme("codeshift-dark");
  };

  /* ================= COPY ================= */

  const handleCopy = async () => {
    if (!value) return;

    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);

      setTimeout(() => {
        setCopied(false);
      }, 1500);

    } catch (err) {
      console.error("Copy failed", err);
    }
  };

  /* ================= DOWNLOAD ================= */

  const handleDownload = () => {
    if (!value) return;

    setDownloading(true);

    setTimeout(() => {
      const blob = new Blob([value], { type: "text/plain" });
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = `converted.${fileExtension(language)}`;
      a.click();

      URL.revokeObjectURL(url);
      setDownloading(false);
    }, 300);
  };

  return (
    <div className="editor-panel">

      {/* ===== Editor Top Bar ===== */}

      <div className="editor-topbar">
        <span>Output Code ({language})</span>

        <div style={{ display: "flex", gap: "10px" }}>

          {/* Download Button */}

          <button
            className={`icon-btn ${downloading ? "loading" : ""}`}
            onClick={handleDownload}
            disabled={downloading}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 3v12" />
              <path d="M7 10l5 5 5-5" />
              <path d="M5 21h14" />
            </svg>

            {downloading ? "Downloading..." : "Download"}
          </button>

          {/* Copy Button */}

          <button
            className="icon-btn"
            onClick={handleCopy}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path
                d="M5 15H4a2 2 0 0 1-2-2V4
                a2 2 0 0 1 2-2h9
                a2 2 0 0 1 2 2v1"
              />
            </svg>

            {copied ? "Copied ✓" : "Copy"}
          </button>

        </div>
      </div>

      {/* ===== Monaco Editor ===== */}

      <Editor
        height="460px"
        language={monacoLanguage(language)}
        value={value}
        onMount={handleEditorDidMount}
        theme="codeshift-dark"
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          fontFamily: "Fira Code",
          lineNumbers: "on",
          readOnly: false,
          scrollBeyondLastLine: false,
          automaticLayout: true,
          wordWrap: "on",
          smoothScrolling: true,
          cursorBlinking: "smooth",
          padding: { top: 16 }
        }}
      />

    </div>
  );
}