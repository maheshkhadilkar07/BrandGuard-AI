import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Alert, Card, Empty, PageHeader, Spinner, fmtDate } from '../components/UI';
import { SeverityBadge, StatusBadge } from '../components/Badges';
import Highlighted from '../components/Highlighted';
import IssueCard from '../components/IssueCard';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { ReviewsList, useContent } from './ContentResults';
import { useEffect } from 'react';

export function ReviewQueue() {
  const [rows, setRows] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState('');
  useEffect(() => {
    api.get('/reviews/queue').then(setRows).catch((e) => setError(e.message));
    api.get('/reviews').then(setHistory).catch(() => {});
  }, []);
  return (
    <>
      <PageHeader title="Review queue" subtitle="Content submitted by creators and waiting for a human decision." />
      <Alert>{error}</Alert>
      <Card title="Awaiting review">
        {!rows ? <Spinner /> : rows.length === 0 ? <Empty>Nothing is waiting for review.</Empty> : (
          <table className="table"><thead><tr><th>Title</th><th>Creator</th><th>Submitted</th><th>Issues</th><th /></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.id}><td><strong>{r.title}</strong></td><td>{r.creator_name}</td><td>{fmtDate(r.submitted_at)}</td>
                <td>{Object.entries(r.severity_counts).map(([s, n]) => <span key={s} style={{ marginRight: 6 }}><SeverityBadge severity={s} /> {n}</span>)}{r.issue_count === 0 && '0'}</td>
                <td><Link className="btn btn-primary" to={`/review/${r.id}`}>Review</Link></td></tr>))}</tbody></table>
        )}
      </Card>
      <Card title="Previous decisions">
        {history.length === 0 ? <Empty>No decisions recorded yet.</Empty> : (
          <table className="table"><thead><tr><th>Content</th><th>Decision</th><th>Reviewer</th><th>Comment</th><th>When</th></tr></thead>
            <tbody>{history.map((h) => <tr key={h.id}><td><Link to={`/content/${h.submission_id}`}>{h.content_title}</Link></td><td><StatusBadge status={h.decision} /></td><td>{h.reviewer_name}</td><td>{h.comment || '—'}</td><td>{fmtDate(h.decided_at)}</td></tr>)}</tbody></table>
        )}
      </Card>
    </>
  );
}

export default function Review() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { c, setC, error, setError } = useContent(id);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState('');
  const [active, setActive] = useState(null);

  if (error && !c) return <Alert>{error}</Alert>;
  if (!c) return <Spinner />;
  const canDecide = user.role === 'reviewer' && c.status === 'submitted';
  const needsVerification = c.issues.filter((i) => i.requires_human_verification).length;

  const decide = async (decision) => {
    if (decision !== 'approved' && !comment.trim()) return setError('Please write a reason or comment for this decision.');
    if (decision === 'approved' && c.issues.some((i) => ['Critical', 'High'].includes(i.severity)) &&
      !window.confirm('This content still has Critical or High findings. Approve anyway?')) return;
    setBusy(decision); setError('');
    try { setC(await api.post(`/content/${id}/review`, { decision, comment })); setComment(''); }
    catch (e) { setError(e.message); } finally { setBusy(''); }
  };

  return (
    <>
      <PageHeader title={`Review: ${c.title}`} subtitle={`Submitted by ${c.creator_name} · ${fmtDate(c.submitted_at)}`}
        actions={<><StatusBadge status={c.status} /><Link className="btn btn-outline" to="/review">← Queue</Link></>} />
      <Alert kind="info">Automated findings below are advisory. You make the final decision; the system never approves content by itself.</Alert>
      <Alert onClose={() => setError('')}>{error}</Alert>
      {needsVerification > 0 && <Alert kind="warn">{needsVerification} finding(s) need human verification because the system could not confirm them.</Alert>}
      <div className="grid-results">
        <Card title="Content"><Highlighted text={c.current_text} issues={c.issues} activeId={active} onSelect={setActive} />
          {c.revised_text != null && <details><summary>Show creator’s original text</summary><div className="doc-text">{c.original_text}</div></details>}</Card>
        <Card title={`AI-detected findings (${c.issues.length})`}>
          {c.issues.length === 0 ? <Empty>No issues were found by the stored rules.</Empty> : c.issues.map((i) => (
            <IssueCard key={i.id} issue={i} active={active === i.id} onClick={() => setActive(i.id)}>
              {i.suggestion && <p className="small"><strong>Creator’s handling:</strong> {{ pending: 'No decision', accepted: 'Accepted suggestion', edited: 'Edited and accepted', rejected: 'Rejected suggestion' }[i.suggestion.status]}</p>}
            </IssueCard>))}
        </Card>
      </div>
      <Card title="Decision">
        {canDecide ? (
          <div className="form">
            <label><span>Comment (required to reject or request changes)</span>
              <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} /></label>
            <div className="row gap wrap">
              <button className="btn btn-success" disabled={!!busy} onClick={() => decide('approved')}>{busy === 'approved' ? '…' : 'Approve'}</button>
              <button className="btn btn-warn" disabled={!!busy} onClick={() => decide('changes_requested')}>Request changes</button>
              <button className="btn btn-danger" disabled={!!busy} onClick={() => decide('rejected')}>Reject</button>
            </div>
          </div>
        ) : <p className="muted">{c.status === 'submitted' ? 'Only reviewers can record a decision.' : 'No decision is needed for this status.'}</p>}
        <h4>Review history</h4>
        <ReviewsList reviews={c.reviews} />
      </Card>
    </>
  );
}
