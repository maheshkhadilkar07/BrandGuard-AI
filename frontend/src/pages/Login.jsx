import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Alert } from '../components/UI';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setBusy(true);
    try { await login(email, password); navigate('/'); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const fill = (e, p) => { setEmail(e); setPassword(p); };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand center"><span className="logo">B</span><div><strong>BrandGuard AI</strong><small>Brand governance and content compliance</small></div></div>
        <h2>Sign in</h2>
        <Alert>{error}</Alert>
        <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        <button className="btn btn-primary block" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <p className="muted center-text">New content creator? <Link to="/register">Create an account</Link></p>
        <div className="demo-box">
          <strong>Demonstration accounts</strong> (fictional company data)
          <div className="row wrap gap-s">
            <button type="button" className="btn btn-outline" onClick={() => fill('admin@technova.demo', 'Admin@123')}>Admin</button>
            <button type="button" className="btn btn-outline" onClick={() => fill('creator@technova.demo', 'Creator@123')}>Creator</button>
            <button type="button" className="btn btn-outline" onClick={() => fill('reviewer@technova.demo', 'Reviewer@123')}>Reviewer</button>
          </div>
          <small className="muted">Buttons only fill in the form. Press “Sign in” to continue.</small>
        </div>
      </form>
    </div>
  );
}
