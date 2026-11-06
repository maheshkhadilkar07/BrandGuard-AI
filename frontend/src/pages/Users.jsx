import { useEffect, useState } from 'react';
import { Alert, Card, Empty, Modal, PageHeader, Spinner, fmtDate } from '../components/UI';
import { Pill } from '../components/Badges';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState(null);
  const [audit, setAudit] = useState([]);
  const [org, setOrg] = useState(null);
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [editOrg, setEditOrg] = useState(false);

  const load = () => {
    api.get('/users').then(setUsers).catch((e) => setError(e.message));
    api.get('/audit?limit=50').then(setAudit).catch(() => {});
    api.get('/organisation').then(setOrg).catch(() => {});
  };
  useEffect(load, []);
  const patch = async (u, body) => { try { await api.patch(`/users/${u.id}`, body); load(); } catch (e) { setError(e.message); } };

  return (
    <>
      <PageHeader title="Users & audit log" subtitle="Manage accounts, roles and review the activity trail." />
      <Alert onClose={() => setError('')}>{error}</Alert>
      {org && (
        <Card title="Organisation profile" actions={<button className="btn btn-outline" onClick={() => setEditOrg(true)}>Edit</button>}>
          <strong>{org.name}</strong> {org.is_demo && <Pill kind="warn">Demonstration data</Pill>}
          <p className="muted">{org.industry || 'No industry set'} · Brand voice: {org.brand_voice || '—'}</p>
          <p>{org.description}</p>
        </Card>
      )}
      <Card title="Users" actions={<button className="btn btn-primary" onClick={() => setAdding(true)}>+ Add user</button>}>
        {!users ? <Spinner /> : (
          <div className="table-wrap"><table className="table"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th /></tr></thead>
            <tbody>{users.map((u) => (
              <tr key={u.id} className={u.is_active ? '' : 'inactive'}><td>{u.full_name}</td><td>{u.email}</td>
                <td><select value={u.role} disabled={u.id === me.id} onChange={(e) => patch(u, { role: e.target.value })} aria-label={`Role of ${u.full_name}`}>
                  <option value="admin">Admin</option><option value="creator">Creator</option><option value="reviewer">Reviewer</option></select></td>
                <td><Pill kind={u.is_active ? 'good' : 'neutral'}>{u.is_active ? 'Active' : 'Deactivated'}</Pill></td>
                <td>{u.id !== me.id && <button className="btn btn-ghost" onClick={() => patch(u, { is_active: !u.is_active })}>{u.is_active ? 'Deactivate' : 'Activate'}</button>}</td></tr>))}</tbody></table></div>
        )}
      </Card>
      <Card title="Audit log (latest 50)">
        {audit.length === 0 ? <Empty>No entries.</Empty> : (
          <div className="table-wrap"><table className="table"><thead><tr><th>When</th><th>User</th><th>Action</th><th>Details</th></tr></thead>
            <tbody>{audit.map((a) => <tr key={a.id}><td className="nowrap">{fmtDate(a.created_at)}</td><td>{a.user || '—'}</td><td>{a.action}</td><td className="small">{a.entity_type ? `${a.entity_type} #${a.entity_id} ` : ''}{a.details || ''}</td></tr>)}</tbody></table></div>
        )}
      </Card>
      {adding && <AddUser onClose={() => setAdding(false)} onSaved={() => { setAdding(false); load(); }} />}
      {editOrg && <EditOrg org={org} onClose={() => setEditOrg(false)} onSaved={() => { setEditOrg(false); load(); }} />}
    </>
  );
}

function AddUser({ onClose, onSaved }) {
  const [f, setF] = useState({ full_name: '', email: '', password: '', role: 'creator' });
  const [error, setError] = useState('');
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async (e) => { e.preventDefault(); try { await api.post('/users', f); onSaved(); } catch (err) { setError(err.message); } };
  return (
    <Modal title="Add user" onClose={onClose}>
      <form className="form" onSubmit={save}><Alert>{error}</Alert>
        <label><span>Full name</span><input value={f.full_name} onChange={set('full_name')} required /></label>
        <label><span>Email</span><input type="email" value={f.email} onChange={set('email')} required /></label>
        <label><span>Temporary password (min 8)</span><input type="password" minLength={8} value={f.password} onChange={set('password')} required /></label>
        <label><span>Role</span><select value={f.role} onChange={set('role')}><option value="creator">Content Creator</option><option value="reviewer">Reviewer</option><option value="admin">Admin</option></select></label>
        <div className="row gap end"><button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button><button className="btn btn-primary">Create</button></div>
      </form>
    </Modal>
  );
}

function EditOrg({ org, onClose, onSaved }) {
  const [f, setF] = useState({ name: org.name, industry: org.industry || '', description: org.description || '', brand_voice: org.brand_voice || '' });
  const [error, setError] = useState('');
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async (e) => { e.preventDefault(); try { await api.put('/organisation', f); onSaved(); } catch (err) { setError(err.message); } };
  return (
    <Modal title="Organisation profile" onClose={onClose}>
      <form className="form" onSubmit={save}><Alert>{error}</Alert>
        <label><span>Name</span><input value={f.name} onChange={set('name')} required /></label>
        <label><span>Industry</span><input value={f.industry} onChange={set('industry')} /></label>
        <label><span>Brand voice</span><input value={f.brand_voice} onChange={set('brand_voice')} /></label>
        <label><span>Description</span><textarea rows={3} value={f.description} onChange={set('description')} /></label>
        <div className="row gap end"><button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button><button className="btn btn-primary">Save</button></div>
      </form>
    </Modal>
  );
}
