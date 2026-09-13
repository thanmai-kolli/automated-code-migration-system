import { useEffect, useRef, useState } from "react";


export default function HowItWorks() {
  return (
    <section className="how-section">

      <div className="how-header">
        <h2>
          Three Steps to <span className="highlight">Migrated Code</span>
        </h2>
      </div>

      <div className="how-steps">
                <StepCard
        number={1}
        icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="4" width="18" height="14" rx="2" />
            <path d="M8 20h8" />
            </svg>
        }
        title="Input Your Code"
        text="Paste code or upload a file in Java, Python, C, or C++."
        />

        <StepCard
        number={2}
        icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M8 7l-5 5 5 5" />
            <path d="M16 7l5 5-5 5" />
            </svg>
        }
        title="Choose Migration Type"
        text="Select cross-language conversion or version upgrade with target settings."
        />

        <StepCard
        number={3}
        icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 12l2 2 4-4" />
            <rect x="3" y="3" width="18" height="18" rx="2" />
            </svg>
        }
        title="Review & Validate"
        text="Edit the output, add test cases, and verify correctness instantly."
        />
      </div>

    </section>
  );
}

/* ---------------- STEP CARD ---------------- */

function StepCard({ number, icon, title, text }) {
  const ref = useRef();
  const [visible, setVisible] = useState(false);
  const [count, setCount] = useState(0);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          animateNumber();
        }
      },
      { threshold: 0.4 }
    );

    if (ref.current) observer.observe(ref.current);

    return () => observer.disconnect();
  }, []);

  const animateNumber = () => {
    let start = 0;
    const interval = setInterval(() => {
      start++;
      setCount(start);
      if (start >= number) clearInterval(interval);
    }, 150);
  };

  return (
    <div
      ref={ref}
      className={`step-card ${visible ? "fade-in-up" : ""}`}
    >
      <div className="step-number">
        {String(count).padStart(2, "0")}
      </div>

        <div className="step-content">
            <div className="step-title-row">
                <div className="step-icon">{icon}</div>
                <h3>{title}</h3>
            </div>
            <p>{text}</p>
        </div>
    </div>
  );
}