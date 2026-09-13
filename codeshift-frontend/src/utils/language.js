const MONACO_IDS = {
  java: "java",
  python: "python",
  c: "c",
  "c++": "cpp",
  cpp: "cpp",
};

const FILE_EXTENSIONS = {
  java: "java",
  python: "py",
  c: "c",
  "c++": "cpp",
  cpp: "cpp",
};

export function monacoLanguage(label) {
  return MONACO_IDS[label?.toLowerCase()] || "plaintext";
}

export function fileExtension(label) {
  return FILE_EXTENSIONS[label?.toLowerCase()] || "txt";
}
