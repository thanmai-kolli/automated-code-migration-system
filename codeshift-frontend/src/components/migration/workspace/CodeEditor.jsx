// // // export default function CodeEditor({
// // //   language,
// // //   value,
// // //   onChange,
// // //   onUpload
// // // }) {
// // //   return (
// // //     <div className="editor-panel">

// // //       <div className="editor-topbar">
// // //         <span>Source Code ({language})</span>

// // //         <label className="upload-btn">
// // //           Upload File
// // //           <input
// // //             type="file"
// // //             accept=".java,.py,.c,.cpp,.txt"
// // //             hidden
// // //             onChange={onUpload}
// // //           />
// // //         </label>
// // //       </div>

// // //       <textarea
// // //         className="editor-area"
// // //         value={value}
// // //         onChange={(e) => onChange(e.target.value)}
// // //         placeholder="Paste your source code here..."
// // //       />

// // //     </div>
// // //   );
// // // }
// import { useRef } from "react";

// export default function CodeEditor({
//   language,
//   value,
//   onChange,
//   onUpload
// }) {
//   const textareaRef = useRef(null);
//   const lineRef = useRef(null);

//   const handleScroll = () => {
//     if (lineRef.current && textareaRef.current) {
//       lineRef.current.scrollTop = textareaRef.current.scrollTop;
//     }
//   };

//   const lines = value.split("\n").length;

//   return (
//     <div className="editor-panel">

//       <div className="editor-topbar">
//         <span>Source Code ({language})</span>

//         <label className="upload-icon-btn">
//           📂 Upload
//           <input
//             type="file"
//             accept=".java,.py,.c,.cpp,.txt"
//             hidden
//             onChange={onUpload}
//           />
//         </label>
//       </div>

//       <div className="editor-body">

//         <div className="line-numbers" ref={lineRef}>
//           {Array.from({ length: lines }, (_, i) => (
//             <div key={i}>{i + 1}</div>
//           ))}
//         </div>

//         {/* <textarea
//           ref={textareaRef}
//           className="editor-area"
//           value={value}
//           onChange={(e) => onChange(e.target.value)}
//           onScroll={handleScroll}
//           placeholder="Paste your source code here..."
//         /> */}
//         <textarea
//           className="editor-area auto-grow"
//           value={value}
//           onChange={(e) => {
//             onChange(e.target.value);
//             e.target.style.height = "auto";
//             e.target.style.height = e.target.scrollHeight + "px";
//             placeholder="Paste your source code here..."
//           }}
//           rows={1}
//         />
//       </div>

//     </div>
//   );
// }
// // import { useEffect, useRef, useState } from "react";

// // export default function CodeEditor({
// //   language,
// //   value,
// //   onChange,
// //   readOnly = false
// // }) {
// //   const textareaRef = useRef(null);
// //   const [lineNumbers, setLineNumbers] = useState([1]);

// //   useEffect(() => {
// //     const lines = value.split("\n").length;
// //     setLineNumbers(Array.from({ length: lines }, (_, i) => i + 1));
// //   }, [value]);

// //   const handleChange = (e) => {
// //     onChange && onChange(e.target.value);

// //     // Auto-grow until max height
// //     e.target.style.height = "auto";
// //     e.target.style.height = e.target.scrollHeight + "px";
// //   };

// //   const syncScroll = () => {
// //     const lineContainer = textareaRef.current.previousSibling;
// //     lineContainer.scrollTop = textareaRef.current.scrollTop;
// //   };

// //   return (
// //     <div className="editor-panel">

// //       <div className="editor-topbar">
// //         <span>{language}</span>
// //       </div>

// //       <div className="editor-container">

// //         <div className="line-numbers">
// //           {lineNumbers.map((num) => (
// //             <div key={num}>{num}</div>
// //           ))}
// //         </div>

// //         <textarea
// //           ref={textareaRef}
// //           className="editor-area"
// //           value={value}
// //           onChange={handleChange}
// //           onScroll={syncScroll}
// //           readOnly={readOnly}
// //         />

// //       </div>
// //     </div>
// //   );
// // }
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