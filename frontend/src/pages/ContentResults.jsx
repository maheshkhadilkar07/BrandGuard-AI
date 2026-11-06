import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Alert, Card, Empty, Modal, PageHeader, Spinner, fmtDate } from '../components/UI';
import { Pill, SeverityBadge, StatusBadge } from '../components/Badges';
import Highlighted from '../components/Highlighted';
import IssueCard from '../components/IssueCard';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

const EDITABLE = ['draft', 'analyzed', 'changes_requested'];
const SEVS = ['Critical', 'High', 'Medium', 'Low'];

export function useContent(id) {
  const [c, setC] = useState(null);
  const [error, setError] = useState('');
  const load = useCallback(() => api.get(`/content/${id}`).then(setC).catch((e) => setError(e.message)), [id]);
  useEffect(() => { load(); }, [load]);
  return { c, setC, error, setError, reload: load };
}

export function ReviewsList({ reviews }) {
  if (!reviews.length) return <Empty>No reviewer decisions yet.</Empty>;
  return (
    <ul className="activity">
      {reviews.map((r) => (
        <li key={r.id}><StatusBadge status={r.decision} /> <strong>{r.reviewer_name}</strong>
          <div>{r.comment || <span className="muted">No comment.</span>}</div>
          <div className="muted small">{fmtDate(r.decided_at)}</div></li>
      ))}
    </ul>
  );
}

export default function ContentResults() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { c, setC, error, setError, reload } = useContent(id);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState('');
  const [editing, setEditing] = useState(false);
  const [info, setInfo] = useState('');

  const isOwner = user.role === 'creator' && c && c.creator_id === user.id;
  const editable = c && EDITABLE.includes(c.status);
  const counts = useMemo(() => {
    const m = { Critical: 0, High: 0, Medium: 0, Low: 0 };
    (c?.issues || []).forEach((i) => { m[i.severity] += 1; });
    return m;
  }, [c]);

  if (error && !c) return <Alert>{error}</Alert>;
  if (!c) return <Spinner />;

  const act = async (key, fn) => {
    setBusy(key); setError(''); setInfo('');
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(''); }
  };
  const analyze = () => act('analyze', async () => setC(await api.post(`/content/${id}/analyze`)));
  const submit = () => act('submit', async () => { setC(await api.post(`/content/${id}/submit`)); setInfo('Submitted for human review.'); });
  const remove = () => act('del', async () => {
    if (!window.confirm('Delete this draft?')) return;
    await api.del(`/content/${id}`); navigate('/content');
  });
  const stale = c.status === 'draft' && c.run_count > 0;
  const hasSuggestions = c.issues.some((i) => i.suggestion);
  const lastRun = c.runs[0];

  return (
    <>
      <PageHeader title={c.title} subtitle={`By ${c.creator_name} · ${c.source_type.toUpperCase()}${c.original_filename ? ` · ${c.original_filename}` : ''} · updated ${fmtDate(c.updated_at)}`}
        actions={<>
          <StatusBadge status={c.status} />
          {isOwner && editable && <button className="btn btn-outline" onClick={() => setEditing(true)}>Edit text</button>}
          {isOwner && editable && <button className="btn btn-primary" onClick={analyze} disabled={!!busy}>{busy === 'analyze' ? 'Analyzing…' : c.run_count ? 'Re-run compliance check' : 'Run compliance check'}</button>}
        </>} />
      <Alert onClose={() => setError('')}>{error}</Alert>
      <Alert kind="success" onClose={() => setInfo('')}>{info}</Alert>
      {stale && <Alert kind="warn">The text has changed since the last check. Run the compliance check again before submitting.</Alert>}
      {c.status === 'changes_requested' && <Alert kind="warn">A reviewer asked for changes. See their comment below, update the content and run the check again.</Alert>}
      {c.extraction_meta?.warnings?.map((w) => <Alert key={w} kind="warn">{w}</Alert>)}

      <div className="summary-bar">
        {SEVS.map((s) => <div key={s} className={`sum sev-${s.toLowerCase()}`}><b>{counts[s]}</b> {s}</div>)}
        {lastRun && <div className="muted small">Run {lastRun.run_number} · {lastRun.issue_count} issue(s) · {lastRun.ai_status.split('|')[0]}</div>}
      </div>

      <div className="grid-results">
        <Card title="Content">
          {c.revised_text != null && <Alert kind="info">Showing the revised text. The original is kept unchanged below.</Alert>}
          <Highlighted text={c.current_text} issues={stale ? [] : c.issues} activeId={active}
            onSelect={(i) => { setActive(i); document.getElementById(`issue-${i}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }} />
          {c.revised_text != null && (
            <details><summary>Show original text</summary><div className="doc-text">{c.original_text}</div></details>
          )}
        </Card>
        <div>
          <Card title={`Detected issues (${c.issues.length})`}
            actions={isOwner && editable && hasSuggestions && <Link className="btn btn-outline" to={`/content/${id}/suggestions`}>Review suggestions</Link>}>
            <p className="muted small">Findings are automated and may be wrong. “Requires human verification” means the system could not confirm the issue itself.</p>
            {c.run_count === 0 ? <Empty>Not analysed yet. {isOwner ? 'Press “Run compliance check”.' : ''}</Empty>
              : c.issues.length === 0 ? <Empty>No issues found by the stored rules. A human reviewer should still check the content.</Empty>
              : c.issues.map((i) => <IssueCard key={i.id} issue={i} active={active === i.id} onClick={() => setActive(i.id)} />)}
          </Card>
        </div>
      </div>

      <Card title="Review status and feedback"
        actions={isOwner && c.status === 'analyzed' && <button className="btn btn-primary" onClick={submit} disabled={!!busy}>{busy === 'submit' ? 'Submitting…' : 'Submit for review'}</button>}>
        {isOwner && c.status === 'draft' && <p className="muted">Run the compliance check, handle the suggestions, then submit for review.</p>}
        {isOwner && c.status === 'analyzed' && <p className="muted">Issues may remain open. The reviewer will see all findings. Only a human reviewer can approve.</p>}
        {c.status === 'submitted' && <p>Waiting for a reviewer. Submitted {fmtDate(c.submitted_at)}.</p>}
        <ReviewsList reviews={c.reviews} />
        {(user.role === 'reviewer' && c.status === 'submitted') && <Link className="btn btn-primary" to={`/review/${c.id}`}>Open review screen</Link>}
        {isOwner && c.status === 'draft' && <button className="btn btn-ghost danger" onClick={remove}>Delete draft</button>}
      </Card>

      <Card title="Analysis history">
        {c.runs.length === 0 ? <Empty>No analyses yet.</Empty> : (
          <table className="table"><thead><tr><th>Run</th><th>When</th><th>Issues</th><th>AI layer</th></tr></thead>
            <tbody>{c.runs.map((r) => <tr key={r.run_number}><td>#{r.run_number}</td><td>{fmtDate(r.created_at)}</td><td>{r.issue_count}</td><td className="small">{r.ai_status}</td></tr>)}</tbody></table>
        )}
      </Card>

      {editing && <EditModal c={c} onClose={() => setEditing(false)} onSaved={(n) => { setC(n); setEditing(false); }} />}
    </>
  );
}

function EditModal({ c, onClose, onSaved }) {
  const [title, setTitle] = useState(c.title);
  const [text, setText] = useState(c.current_text);
  const [error, setError] = useState('');
  const save = async (e) => {
    e.preventDefault();
    try { onSaved(await api.put(`/content/${c.id}`, { title, text })); } catch (err) { setError(err.message); }
  };
  return (
    <Modal title="Edit content" onClose={onClose} wide>
      <form className="form" onSubmit={save}>
        <Alert>{error}</Alert>
        <label><span>Title</span><input value={title} onChange={(e) => setTitle(e.target.value)} required /></label>
        <label><span>Text</span><textarea rows={12} value={text} onChange={(e) => setText(e.target.value)} required /></label>
        <small className="muted">Saving replaces the text and returns the content to Draft, so it must be checked again.</small>
        <div className="row gap end"><button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button><button className="btn btn-primary">Save</button></div>
      </form>
    </Modal>
  );
}
