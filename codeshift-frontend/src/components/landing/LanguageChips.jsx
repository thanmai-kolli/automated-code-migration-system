

export default function LanguageChips() {
  const languages = ["Java", "Python", "C", "C++"];

  return (
    <section className="section">
      <div className="container chips-container">
        {languages.map((lang) => (
          <div key={lang} className="chip">
            {lang}
          </div>
        ))}
      </div>
    </section>
  );
}