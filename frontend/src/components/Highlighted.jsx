// Shows the analysed text with problem phrases highlighted by severity. Clicking a highlight selects the issue.
export default function Highlighted({ text, issues, onSelect, activeId }) {
  const spans = issues
    .filter((i) => i.start_char != null && i.end_char != null && text.slice(i.start_char, i.end_char) === i.flagged_text)
    .sort((a, b) => a.start_char - b.start_char);
  const parts = [];
  let pos = 0;
  spans.forEach((i) => {
    if (i.start_char < pos) return; // skip overlaps
    if (i.start_char > pos) parts.push(<span key={`t${pos}`}>{text.slice(pos, i.start_char)}</span>);
    parts.push(
      <mark key={i.id} className={`hl sev-${i.severity.toLowerCase()} ${activeId === i.id ? 'active' : ''}`}
        onClick={() => onSelect && onSelect(i.id)} title={`${i.severity}: ${i.title}`}>
        {text.slice(i.start_char, i.end_char)}
      </mark>,
    );
    pos = i.end_char;
  });
  if (pos < text.length) parts.push(<span key="end">{text.slice(pos)}</span>);
  return <div className="doc-text">{parts}</div>;
}
