import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Alert } from '../components/UI';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [orgs, setOrgs] = useState(null);
  const [f, setF] = useState({ full_name: '', email: '', password: '', organisation_id: '', organisation_name: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => { api.get('/organisations/public').then(setOrgs).catch((e) => setError(e.message)); }, []);
  const first = orgs && orgs.length === 0;

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setBusy(true);
    try {
      const body = { full_name: f.full_name, email: f.email, password: f.password };
      if (first) body.organisation_name = f.organisation_name;
      else body.organisation_id = Number(f.organisation_id);
      await register(body);
      navigate('/');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand center"><span className="logo">B</span><div><strong>BrandGuard AI</strong><small>Create your account</small></div></div>
        <h2>Register</h2>
        {first && <Alert kind="info">No organisation exists yet. You will become its administrator.</Alert>}
        {!first && orgs && <Alert kind="info">Self-registration creates a Content Creator account. An administrator can give you other roles.</Alert>}
        <Alert>{error}</Alert>
        <label>Full name<input value={f.full_name} onChange={set('full_name')} required minLength={2} /></label>
        <label>Email<input type="email" value={f.email} onChange={set('email')} required /></label>
        <label>Password (at least 8 characters)<input type="password" value={f.password} onChange={set('password')} required minLength={8} /></label>
        {first && <label>Organisation name<input value={f.organisation_name} onChange={set('organisation_name')} required /></label>}
        {orgs && !first && (
          <label>Organisation
            <select value={f.organisation_id} onChange={set('organisation_id')} required>
              <option value="">Select…</option>
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </label>
        )}
        <button className="btn btn-primary block" disabled={busy || !orgs}>{busy ? 'Creating…' : 'Create account'}</button>
        <p className="muted center-text">Already registered? <Link to="/login">Sign in</Link></p>
      </form>
    </div>
  );
}
