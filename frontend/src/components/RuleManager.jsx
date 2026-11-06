import { useCallback, useEffect, useState } from 'react';
import { Alert, Card, Empty, Modal, Spinner } from './UI';
import { Pill } from './Badges';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

/**
 * Generic list + add/edit/delete screen for one kind of brand rule.
 * config = { path, noun, fields: [{name,label,type,options,help,required,show}], columns: [{label, render}],
 *            blank, toForm(row), toPayload(form) }
 */
export default function RuleManager({ config }) {
  const { user } = useAuth();
  const isAdmin = user.role === 'admin';
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(null); // null | {id?, form}

  const load = useCallback(() => api.get(config.path).then(setRows).catch((e) => setError(e.message)), [config.path]);
  useEffect(() => { setRows(null); load(); }, [load]);

  const remove = async (row) => {
    if (!window.confirm(`Delete this ${config.noun}? Past findings keep their saved copy of the rule.`)) return;
    try { await api.del(`${config.path}/${row.id}`); load(); } catch (e) { setError(e.message); }
  };
  const toggle = async (row) => {
    try { await api.put(`${config.path}/${row.id}`, { ...config.toPayload(config.toForm(row)), is_active: !row.is_active }); load(); }
    catch (e) { setError(e.message); }
  };

  return (
    <Card title={config.title} actions={isAdmin && <button className="btn btn-primary" onClick={() => setEditing({ form: { ...config.blank } })}>+ Add {config.noun}</button>}>
      {config.intro && <p className="muted">{config.intro}</p>}
      <Alert onClose={() => setError('')}>{error}</Alert>
      {!isAdmin && <Alert kind="info">You can view these rules. Only administrators can change them.</Alert>}
      {!rows ? <Spinner /> : rows.length === 0 ? <Empty>No {config.noun}s yet.{isAdmin ? ' Add the first one.' : ''}</Empty> : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>ID</th>{config.columns.map((c) => <th key={c.label}>{c.label}</th>)}<th>Status</th>{isAdmin && <th />}</tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className={r.is_active ? '' : 'inactive'}>
                  <td>#{r.id}</td>
                  {config.columns.map((c) => <td key={c.label}>{c.render(r)}</td>)}
                  <td><Pill kind={r.is_active ? 'good' : 'neutral'}>{r.is_active ? 'Active' : 'Inactive'}</Pill></td>
                  {isAdmin && (
                    <td className="nowrap">
                      <button className="btn btn-ghost" onClick={() => setEditing({ id: r.id, form: config.toForm(r) })}>Edit</button>
                      <button className="btn btn-ghost" onClick={() => toggle(r)}>{r.is_active ? 'Deactivate' : 'Activate'}</button>
                      <button className="btn btn-ghost danger" onClick={() => remove(r)}>Delete</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && (
        <RuleForm config={config} initial={editing} onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }} />
      )}
    </Card>
  );
}

function RuleForm({ config, initial, onClose, onSaved }) {
  const [form, setForm] = useState(initial.form);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (name, v) => setForm((f) => ({ ...f, [name]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      const payload = config.toPayload(form);
      if (initial.id) await api.put(`${config.path}/${initial.id}`, payload);
      else await api.post(config.path, payload);
      onSaved();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  return (
    <Modal title={`${initial.id ? 'Edit' : 'Add'} ${config.noun}`} onClose={onClose}>
      <form onSubmit={submit} className="form">
        <Alert>{error}</Alert>
        {config.fields.filter((f) => !f.show || f.show(form)).map((f) => (
          <label key={f.name} className={f.type === 'checkbox' ? 'check' : ''}>
            {f.type !== 'checkbox' && <span>{f.label}{f.required && ' *'}</span>}
            {f.type === 'textarea' ? <textarea rows={3} value={form[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)} required={f.required} />
              : f.type === 'select' ? (
                <select value={form[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)} required={f.required}>
                  {f.options.map((o) => <option key={o[0]} value={o[0]}>{o[1]}</option>)}
                </select>)
              : f.type === 'checkbox' ? <><input type="checkbox" checked={!!form[f.name]} onChange={(e) => set(f.name, e.target.checked)} /><span>{f.label}</span></>
              : <input type={f.type || 'text'} value={form[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)} required={f.required} />}
            {f.help && <small className="muted">{f.help}</small>}
          </label>
        ))}
        <div className="row gap end">
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
        </div>
      </form>
    </Modal>
  );
}
