export default function ModeCard({
  icon,
  title,
  description,
  mode,
  onSelect
}) {
  return (
    <div
      className="migration-mode-card"
      onClick={() => onSelect(mode)}
    >
      <div className="mode-icon">
        {icon}
      </div>

      <h2>{title}</h2>
      <p>{description}</p>

      <div className="mode-footer">
        Continue →
      </div>
    </div>
  );
}