const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

function normalizeReport(data, mode) {
  return {
    engine: data.engine || "cross_language_engine",
    source: data.source || null,
    target: data.target || null,
    detectedVersion: data.detected_version || null,

    compileSuccess: data.compile_success ?? null,
    validationStatus: data.validation_status ?? null,
    testSuccess: data.test_success ?? null,

    riskScore: data.risk_score ?? 0,
    riskLevel: data.risk_level ?? "LOW",
    riskTriggers: data.risk_triggers ?? [],

    confidence: data.confidence ?? data.confidence_score ?? 0,

    accuracy: data.accuracy ?? 0,   // ✅ ADD THIS

    totalDiffChanges: data.total_diff_changes ?? data.diff_count ?? 0,
    diffText: data.diff_text ?? "",

    semanticIssues: data.semantic_issues ?? [],
    timeTakenMs: data.timeTakenMs ?? data.time_taken_ms ?? null
  };
}

export async function runCrossLanguage(code, source, target) {
  const res = await fetch(`${API_BASE}/cross-language`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code,
      source_language: source.toLowerCase(),
      target_language: target.toLowerCase()
    })
  });

  const json = await res.json();
  if (!json.success) throw new Error(json.error || "Migration failed");

  return {
    code: json.data.code,
    report: normalizeReport(json.data, "cross")
  };
}

export async function runVersionUpgrade(code, language) {
  const res = await fetch(`${API_BASE}/version-upgrade`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code,
      language: language.toLowerCase()
    })
  });

  const json = await res.json();
  if (!json.success) throw new Error(json.error || "Migration failed");

  return {
    code: json.data.code,
    report: normalizeReport(json.data, "upgrade")
  };
}
// const API_BASE = "http://127.0.0.1:5000/api";

// /* ==========================
//    LANGUAGE NORMALIZER
// ========================== */

// function normalizeLang(lang) {

//   const map = {
//     "c++": "c++",
//     "cpp": "c++",
//     "c": "c",
//     "python": "python",
//     "java": "java"
//   };

//   return map[lang.toLowerCase()] || lang.toLowerCase();
// }

// /* ==========================
//    REPORT NORMALIZER
// ========================== */

// function normalizeReport(data, mode) {
//   return {
//     engine: data.engine || "cross_language_engine",
//     source: data.source || null,
//     target: data.target || null,
//     detectedVersion: data.detected_version || null,

//     compileSuccess: data.compile_success ?? null,
//     validationStatus: data.validation_status ?? null,
//     testSuccess: data.test_success ?? null,

//     riskScore: data.risk_score ?? 0,
//     riskLevel: data.risk_level ?? "LOW",
//     riskTriggers: data.risk_triggers ?? [],

//     confidence: data.confidence ?? data.confidence_score ?? 0,

//     totalDiffChanges: data.total_diff_changes ?? data.diff_count ?? 0,
//     diffText: data.diff_text ?? "",

//     semanticIssues: data.semantic_issues ?? [],
//     timeTakenMs: data.timeTakenMs ?? data.time_taken_ms ?? null
//   };
// }


// /* ==========================
//    CROSS LANGUAGE API
// ========================== */

// export async function runCrossLanguage(code, source, target) {

//   const res = await fetch(`${API_BASE}/cross-language`, {
//     method: "POST",
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify({
//       code,
//       source_language: normalizeLang(source),
//       target_language: normalizeLang(target)
//     })
//   });

//   const json = await res.json();

//   if (!json.success) {
//     throw new Error(json.error || "Migration failed");
//   }

//   return {
//     code: json.data.code,
//     report: normalizeReport(json.data, "cross")
//   };
// }


// /* ==========================
//    VERSION UPGRADE API
// ========================== */

// export async function runVersionUpgrade(code, language) {

//   const res = await fetch(`${API_BASE}/version-upgrade`, {
//     method: "POST",
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify({
//       code,
//       language: normalizeLang(language)
//     })
//   });

//   const json = await res.json();

//   if (!json.success) {
//     throw new Error(json.error || "Migration failed");
//   }

//   return {
//     code: json.data.code,
//     report: normalizeReport(json.data, "upgrade")
//   };
// }