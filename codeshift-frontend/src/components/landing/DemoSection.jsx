import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Prism from "prismjs";

import "prismjs/components/prism-clike";  // REQUIRED BASE
import "prismjs/components/prism-c";      // REQUIRED BEFORE CPP
import "prismjs/components/prism-cpp";
import "prismjs/components/prism-java";
import "prismjs/components/prism-python";


export default function DemoSection() {
  const navigate = useNavigate();
  useEffect(() => {
    Prism.highlightAll();
  }, []);

  return (
    <section className="demo-section">

      <div className="demo-top-buttons">
        <button className="primary-demo-btn"
          onClick={() => navigate("/migration")}>
          Start Converting →
        </button>
        <span className="how-link">See How It Works</span>
      </div>

      <div className="language-row">
        <div className="lang-chip orange">Java</div>
        <div className="lang-chip yellow">Python</div>
        <div className="lang-chip blue">C</div>
        <div className="lang-chip pink">C++</div>
      </div>

      <div className="code-preview-grid">

        {/* ---------------- PYTHON → JAVA ---------------- */}
        <div className="code-card">

          <div className="editor-bar">
            <div className="dots">
              <span></span><span></span><span></span>
            </div>
            <div className="editor-title">Python → Java</div>
          </div>
        <div className="editor-content">

          <div className="split-code">

            <EditorSide
            //   label="Python"
              language="python"
              lines={6}
              code={`def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)`}
            />

            <EditorSide
            //   label="Java"
              language="java"
              lines={6}
              code={`public static int fibonacci(int n){
    if(n <= 1) return n;
    return fibonacci(n-1) + fibonacci(n-2); }`}
            />
    </div>
          </div>
        </div>

        {/* ---------------- C++ → PYTHON ---------------- */}
        <div className="code-card">

          <div className="editor-bar">
            <div className="dots">
              <span></span><span></span><span></span>
            </div>
            <div className="editor-title">C++ → Python</div>
          </div>
        <div className="editor-content">
            <div className="split-code">

            <EditorSide
            //   label="C++"
              language="cpp"
              lines={6}
              code={`std::vector<int> filter_even(std::vector<int> v) {
    std::vector<int> result; 
std::copy_if(v.begin(), v.end(), std::back_inserter(result),
        [](int x) { return x % 2 == 0; });
    return result; }`}
            />

            <EditorSide
            //   label="Python"
              language="python"
              lines={6}
              code={`def filter_even(v: list[int]) -> list[int]:
    return [x for x in v if x % 2 == 0]`}
            />

          </div>
        </div>
            </div>
      </div>
    </section>
  );
}


/* ---------------- REUSABLE EDITOR SIDE ---------------- */

function EditorSide({ label, language, code, lines }) {
  return (
    <div className="code-side">

      <div className="side-label">{label}</div>

      <div className="editor-body">

        <div className="line-numbers">
          {Array.from({ length: lines }, (_, i) => (
            <span key={i}>{i + 1}</span>
          ))}
        </div>

        <pre>
          <code className={`language-${language}`}>
            {code}
          </code>
        </pre>

      </div>

    </div>
  );
}