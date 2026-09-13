// import { useState } from "react";

// export default function ConfigurationStep({ mode, onBack, onContinue }) {
//   const [sourceLang, setSourceLang] = useState("");
//   const [targetLang, setTargetLang] = useState("");

//   const handleContinue = () => {
//     onContinue({
//       sourceLang,
//       targetLang: mode === "cross" ? targetLang : null,
//     });
//   };

//   return (
//     <div className="migration-type-page">

//       <div className="migration-type-header">
//         <h1>
//           Configure <span className="highlight">Migration</span>
//         </h1>
//         <p>
//           {mode === "cross"
//             ? "Select source and target languages."
//             : "Select the language to upgrade."}
//         </p>
//       </div>

//       <div className="configuration-card">

//         {/* SOURCE */}
//         <div className="config-group">
//           <label>Source Language</label>
//           <select
//             value={sourceLang}
//             onChange={(e) => setSourceLang(e.target.value)}
//           >
//             <option value="">Select Language</option>
//             <option>Java</option>
//             <option>Python</option>
//             <option>C</option>
//             <option>C++</option>
//           </select>
//         </div>

//         {/* TARGET (Cross Only) */}
//         {mode === "cross" && (
//           <div className="config-group">
//             <label>Target Language</label>
//             <select
//               value={targetLang}
//               onChange={(e) => setTargetLang(e.target.value)}
//             >
//               <option value="">Select Language</option>
//               <option>Java</option>
//               <option>Python</option>
//               <option>C</option>
//               <option>C++</option>
//             </select>
//           </div>
//         )}

//         <div className="config-actions">
//           <button className="config-back-btn" onClick={onBack}>
//             ← Back
//           </button>

//           <button
//             className="config-continue-btn"
//             onClick={handleContinue}
//             disabled={
//               !sourceLang ||
//               (mode === "cross" && !targetLang)
//             }
//           >
//             Continue →
//           </button>
//         </div>

//       </div>

//     </div>
//   );
// }
import { useState } from "react";

const LANGUAGES = ["Java", "Python", "C", "C++"];

export default function ConfigurationStep({ mode, onBack, onContinue }) {
  const [sourceLang, setSourceLang] = useState("");
  const [targetLang, setTargetLang] = useState("");

  const getValidTargets = () => {
    if (sourceLang === "Python") return ["Java"];
    if (sourceLang === "Java") return ["Python"];
    if (sourceLang === "C") return ["C++"];
    if (sourceLang === "C++") return ["C"];
    return [];
  };

  const handleContinue = () => {
    onContinue({
      sourceLang,
      targetLang: mode === "cross" ? targetLang : null,
    });
  };

  return (
    <div className="migration-type-page">

      <div className="migration-type-header">
        <h1>
          Configure <span className="highlight">Migration</span>
        </h1>
        <p>
          {mode === "cross"
            ? "Select source and target languages."
            : "Select the language to upgrade."}
        </p>
      </div>

      {/* SOURCE SELECTION */}
      <div className="language-section">
        <h3>Source Language</h3>

        <div className="language-grid">
          {LANGUAGES.map((lang) => (
            <div
              key={lang}
              className={`language-card ${
                sourceLang === lang ? "selected" : ""
              }`}
              onClick={() => {
                setSourceLang(lang);
                setTargetLang("");
              }}
            >
              {lang}
            </div>
          ))}
        </div>
      </div>

      {/* TARGET SELECTION (CROSS ONLY) */}
      {mode === "cross" && sourceLang && (
        <div className="language-section">
          <h3>Target Language</h3>

          <div className="language-grid">
            {getValidTargets().map((lang) => (
              <div
                key={lang}
                className={`language-card ${
                  targetLang === lang ? "selected" : ""
                }`}
                onClick={() => setTargetLang(lang)}
              >
                {lang}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ACTIONS */}
      <div className="config-actions centered-actions">
            <button className="start-btn" onClick={onBack}>
                ← Back
            </button>

            <button
                className="start-btn"
                onClick={handleContinue}
                disabled={
                !sourceLang ||
                (mode === "cross" && !targetLang)
                }
            >
                Continue →
            </button>
        </div>

    </div>
  );
}