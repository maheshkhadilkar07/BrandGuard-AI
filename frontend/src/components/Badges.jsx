export const STATUS_LABEL = {
  draft: 'Draft', analyzed: 'Analyzed', submitted: 'Submitted for Review',
  changes_requested: 'Changes Requested', approved: 'Approved', rejected: 'Rejected',
};

export const StatusBadge = ({ status }) => (
  <span className={`badge status-${status}`}>{STATUS_LABEL[status] || status}</span>
);

export const SeverityBadge = ({ severity }) => (
  <span className={`badge sev-${(severity || '').toLowerCase()}`}>{severity}</span>
);

export const Pill = ({ children, kind = 'neutral', title }) => (
  <span className={`pill pill-${kind}`} title={title}>{children}</span>
);
