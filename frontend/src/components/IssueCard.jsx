import { Pill, SeverityBadge } from './Badges';

export default function IssueCard({ issue, active, onClick, children }) {
  const pct = issue.confidence != null ? `${Math.round(issue.confidence * 100)}%` : null;
  return (
    <article id={`issue-${issue.id}`} className={`issue sev-border-${issue.severity.toLowerCase()} ${active ? 'issue-active' : ''}`} onClick={onClick}>
      <header className="issue-head">
        <SeverityBadge severity={issue.severity} />
        <h4>{issue.title}</h4>
      </header>
      <div className="row wrap gap-s">
        <Pill>{issue.category}</Pill>
        <Pill kind={issue.detection_method === 'ai' ? 'ai' : 'rule'}>{issue.detection_method === 'ai' ? 'AI-assisted' : 'Rule-based'}</Pill>
        {pct && <Pill title="How sure the system is. Not a guarantee.">Confidence {pct}</Pill>}
        {issue.requires_human_verification && <Pill kind="warn">Requires human verification</Pill>}
      </div>
      {issue.flagged_text && <p className="flagged">“{issue.flagged_text}”</p>}
      <p>{issue.explanation}</p>
      <div className="source-rule">
        <strong>Source rule:</strong> {issue.rule_reference}
        <div className="muted small">{issue.rule_snapshot}</div>
      </div>
      {children}
    </article>
  );
}
