

export default function Footer() {
  return (
    <footer className="footer">

      <div className="footer-glow"></div>

      <div className="footer-container">

        {/* Brand */}
        <div className="footer-brand">
          <h2>CodeShift</h2>
          <p>
            Automated multi-language code migration platform supporting
            cross-language conversion and version upgrades with ML-powered confidence scoring.
          </p>

          {/* Email Subscription */}
          <div className="subscribe-box">
            <input type="email" placeholder="Enter your email" />
            <button>Subscribe</button>
          </div>

          {/* Social Icons */}
          <div className="social-row">
            <a href="#">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M16 8a6 6 0 01-12 0 6 6 0 0112 0z"/>
                <path d="M12 14v7"/>
              </svg>
            </a>
            <a href="#">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 4s-4 2-10 2-10-2-10-2v14s4 2 10 2 10-2 10-2z"/>
              </svg>
            </a>
            <a href="#">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="2" width="20" height="20" rx="5"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
            </a>
          </div>
        </div>

        {/* Product */}
        <div className="footer-column">
          <h4>Product</h4>
          <ul>
            <li>Cross-Language Conversion</li>
            <li>Version Upgrades</li>
            <li>Test Validation</li>
            <li>Confidence Reports</li>
          </ul>
        </div>

        {/* Resources */}
        <div className="footer-column">
          <h4>Resources</h4>
          <ul>
            <li>Documentation</li>
            <li>API Reference</li>
            <li>Release Notes</li>
            <li>Support</li>
          </ul>
        </div>

        {/* Company */}
        <div className="footer-column">
          <h4>Company</h4>
          <ul>
            <li>About</li>
            <li>Contact</li>
            <li>Privacy Policy</li>
            <li>Terms of Service</li>
          </ul>
        </div>

      </div>

      <div className="footer-divider"></div>

      <div className="footer-bottom">
        © {new Date().getFullYear()} CodeShift. All rights reserved.
      </div>

    </footer>
  );
}