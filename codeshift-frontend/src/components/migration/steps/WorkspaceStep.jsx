import { useState } from "react";
import toast from "react-hot-toast";
import { runCrossLanguage, runVersionUpgrade } from "../../../services/migrationService";
import WorkspaceHeader from "../workspace/WorkSpaceHeader";
import ActionToolbar from "../workspace/ActionToolbar";
import CodeEditor from "../workspace/CodeEditor";
import OutputEditor from "../workspace/OutputEditor";
import TestCasePanel from "../workspace/TestCasePanel";
import ReportPanel from "../report/ReportPanel";
import "../../../styles/workspace.css";

export default function WorkspaceStep({ mode, config, onBack }) {
  const [inputCode, setInputCode] = useState("");
  const [outputCode, setOutputCode] = useState("");
  const [testCases, setTestCases] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);

  // Version-upgrade mode has no target language: output stays in the source language.
  const outputLang = config.targetLang || config.sourceLang;

  const handleRun = async () => {
    if (!inputCode.trim()) return;

    setLoading(true);
    setOutputCode("");
    setReport(null);

    try {
      let result;

      if (mode === "cross") {
        result = await runCrossLanguage(
          inputCode,
          config.sourceLang,
          config.targetLang,
          testCases
        );
      } else {
        result = await runVersionUpgrade(
          inputCode,
          config.sourceLang,
          testCases
        );
      }

      //Slight delay for better animation feel
      setTimeout(() => {
        setOutputCode(result.code);
        setReport(result.report);
        setLoading(false);
      }, 400);
    } catch (error) {
      console.error("Migration Error:", error);
      // fetch() rejects with TypeError only when the request never reached the server.
      toast.error(
        error instanceof TypeError
          ? "Cannot reach the migration API — is the backend running?"
          : error.message || "Migration failed"
      );
      setLoading(false);
    }
  };
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setInputCode(event.target.result);
    };
    reader.readAsText(file);
  };

  return (
    <div className="migration-type-page workspace-page">

      <WorkspaceHeader
        mode={mode}
        config={config}
        onBack={onBack}
      />
      <ActionToolbar
        onRun={handleRun}
        loading={loading}
      />

      {loading && (
        <div className="workspace-loading">
          🚀 Running AI Migration Engine...
        </div>
      )}

      <div className="editor-grid">

        <CodeEditor
          language={config.sourceLang}
          value={inputCode}
          onChange={setInputCode}
          onUpload={handleFileUpload}
        />

        <OutputEditor
          language={outputLang}
          value={outputCode}
        />

      </div>

      <TestCasePanel
        value={testCases}
        onChange={setTestCases}
      />

      <ReportPanel report={report} mode={mode} />

    </div>
  );
}