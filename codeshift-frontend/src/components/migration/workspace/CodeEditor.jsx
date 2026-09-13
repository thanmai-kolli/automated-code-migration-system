import Editor from "@monaco-editor/react";
import { monacoLanguage } from "../../../utils/language";

export default function CodeEditor({
  language,
  value,
  onChange,
  onUpload
}) {

  const handleEditorDidMount = (editor, monaco) => {
    monaco.editor.defineTheme("codeshift-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [],
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

  return (
    <div className="editor-panel">

      <div className="editor-topbar">
        <span>Source Code ({language})</span>

        <label className="icon-btn">
          <svg width="16" height="16" viewBox="0 0 24 24"
            fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round"
            strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <path d="M7 10l5-5 5 5"/>
            <path d="M12 15V5"/>
          </svg>
          Upload
          <input
            type="file"
            hidden
            onChange={onUpload}
          />
        </label>
      </div>

      <Editor
        height="460px"                      // 🔥 Bigger editor
        language={monacoLanguage(language)}
        value={value}
        onChange={onChange}
        onMount={handleEditorDidMount}
        theme="codeshift-dark"
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          fontFamily: "Fira Code",
          lineNumbers: "on",
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