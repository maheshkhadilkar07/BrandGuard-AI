import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Alert, Card, Empty, PageHeader, Spinner } from '../components/UI';
import { Pill, SeverityBadge } from '../components/Badges';
import { api } from '../services/api';
import { useContent } from './ContentResults';

const STATE = { pending: ['Pending', 'neutral'], accepted: ['Accepted', 'good'], edited: ['Edited & accepted', 'good'], rejected: ['Rejected', 'bad'] };

function SuggestionRow({ issue, locked, onChanged, onError }) {
  const s = issue.suggestion;
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(s.final_text ?? s.suggested_text);
  const [busy, setBusy] = useState(false);

  const send = async (body) => {
    setBusy(true); onError('');
    try { await api.patch(`/suggestions/${s.id}`, body); setEditing(false); await onChanged(); }
    catch (e) { onError(e.message); } finally { setBusy(false); }
  };
  const label = s.action === 'append' ? 'Add to the end' : s.suggested_text === '' && s.action === 'replace' ? '(remove this text)' : s.suggested_text;
  const [st, kind] = STATE[s.status];

  return (
    <article className="issue">
      <header className="issue-head"><SeverityBadge severity={issue.severity} /><h4>{issue.title}</h4><Pill kind={kind}>{st}</Pill></header>
      <div className="diff">
        <div><small className="muted">Original</small><div className="diff-old">{issue.flagged_text || <em>(whole document)</em>}</div></div>
        <div className="diff-arrow" aria-hidden>→</div>
        <div><small className="muted">Suggested</small>
          <div className="diff-new">{s.action === 'manual' ? <em>No automatic replacement. Write your own text.</em> : label}</div></div>
      </div>
      <p><strong>Why:</strong> {s.explanation}</p>
      <p className="muted small">Based on: {issue.rule_reference}</p>
      {s.status === 'edited' && <p className="small">Your text: <strong>{s.final_text || '(removed)'}</strong></p>}
      {!locked && (editing ? (
        <div className="form">
          <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} aria-label="Your corrected text" />
          <div className="row gap end">
            <button className="btn btn-outline" onClick={() => setEditing(false)}>Cancel</button>
            <button className="btn btn-primary" disabled={busy} onClick={() => send({ status: 'accepted', final_text: text })}>Accept my text</button>
          </div>
        </div>
      ) : (
        <div className="row gap">
          {s.action !== 'manual' && <button className="btn btn-primary" disabled={busy} onClick={() => send({ status: 'accepted' })}>Accept</button>}
          <button className="btn btn-outline" disabled={busy} onClick={() => { setText(s.final_text ?? (s.suggested_text || issue.flagged_text)); setEditing(true); }}>Edit manually</button>
          <button className="btn btn-outline" disabled={busy} onClick={() => send({ status: 'rejected' })}>Reject</button>
          {s.status !== 'pending' && <button className="btn btn-ghost" disabled={busy} onClick={() => send({ status: 'pending' })}>Reset</button>}
        </div>
      ))}
    </article>
  );
}

export default function Suggestions() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { c, error, setError, reload } = useContent(id);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  if (error && !c) return <Alert>{error}</Alert>;
  if (!c) return <Spinner />;
  const locked = !['draft', 'analyzed', 'changes_requested'].includes(c.status) || c.status === 'draft';
  const issues = c.issues.filter((i) => i.suggestion);
  const accepted = issues.filter((i) => ['accepted', 'edited'].includes(i.suggestion.status)).length;

  const showPreview = async () => {
    setError('');
    try { setPreview(await api.get(`/content/${id}/revised-preview`)); } catch (e) { setError(e.message); }
  };
  const apply = async () => {
    setBusy(true); setError('');
    try { await api.post(`/content/${id}/apply-suggestions`); navigate(`/content/${id}`); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  return (
    <>
      <PageHeader title="Correction suggestions" subtitle={`${c.title} · nothing changes in your content until you apply accepted suggestions.`}
        actions={<Link className="btn btn-outline" to={`/content/${id}`}>← Back to results</Link>} />
      <Alert onClose={() => setError('')}>{error}</Alert>
      {c.status === 'draft' && <Alert kind="warn">This content changed after the last check. Run the compliance check again to get current suggestions.</Alert>}
      <div className="grid-results">
        <div>
          {issues.length === 0 ? <Empty>No suggestions available.</Empty>
            : issues.map((i) => <SuggestionRow key={i.id + i.suggestion.status + (i.suggestion.final_text || '')} issue={i} locked={locked} onChanged={reload} onError={setError} />)}
        </div>
        <Card title="Apply corrections">
          <p>{accepted} of {issues.length} suggestion(s) accepted.</p>
          <p className="muted small">Applying creates a revised version. Your original text is kept. The content returns to Draft so the revised text can be checked again.</p>
          <div className="row gap wrap">
            <button className="btn btn-outline" onClick={showPreview}>Preview revised text</button>
            {!locked && <button className="btn btn-primary" disabled={busy || accepted === 0} onClick={apply}>{busy ? 'Applying…' : 'Apply accepted suggestions'}</button>}
          </div>
          {preview && (
            <>
              <p className="muted small">Preview · {preview.applied} change(s) applied{preview.skipped ? `, ${preview.skipped} skipped` : ''}</p>
              <div className="doc-text">{preview.revised_text}</div>
            </>
          )}
        </Card>
      </div>
    </>
  );
}
