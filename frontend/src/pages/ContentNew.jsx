import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Card, PageHeader } from '../components/UI';
import { api } from '../services/api';

const MAX_MB = 10;
const OK_EXT = ['.txt', '.pdf', '.docx', '.png', '.jpg', '.jpeg'];

const SAMPLE = `Introducing Tech Nova Cloud, India's No. 1 cloud platform! Get started for only ₹1,299 per month with 100% guaranteed results. TechNova Cloud launched in 2022 and includes a 30-day free trial. Our AMAZING team is gonna make your migration painless. Enjoy a 99.9% uptime SLA on every plan.`;

export default function ContentNew() {
  const navigate = useNavigate();
  const [mode, setMode] = useState('text');
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const pick = (f) => {
    setError('');
    if (!f) return setFile(null);
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!OK_EXT.includes(ext)) { setFile(null); return setError(`Unsupported file type. Allowed: ${OK_EXT.join(', ')}`); }
    if (f.size > MAX_MB * 1024 * 1024) { setFile(null); return setError(`File is too large (limit ${MAX_MB} MB).`); }
    setFile(f);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setBusy(true);
    try {
      let created;
      if (mode === 'text') created = await api.post('/content', { title, text });
      else {
        if (!file) throw new Error('Please choose a file.');
        const form = new FormData();
        form.append('file', file);
        if (title.trim()) form.append('title', title.trim());
        created = await api.upload('/content/upload', form);
      }
      navigate(`/content/${created.id}`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  return (
    <>
      <PageHeader title="New content" subtitle="Enter text or upload a file. You will check it against the brand rules on the next screen." />
      <Card>
        <div className="tabs">
          <button type="button" className={`tab ${mode === 'text' ? 'active' : ''}`} onClick={() => setMode('text')}>Enter text</button>
          <button type="button" className={`tab ${mode === 'file' ? 'active' : ''}`} onClick={() => setMode('file')}>Upload file</button>
        </div>
        <form className="form" onSubmit={submit}>
          <Alert onClose={() => setError('')}>{error}</Alert>
          <label><span>Title {mode === 'text' && '*'}</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required={mode === 'text'} placeholder="e.g. Spring campaign email" /></label>
          {mode === 'text' ? (
            <label><span>Content *</span>
              <textarea rows={12} value={text} onChange={(e) => setText(e.target.value)} required placeholder="Paste or type your content here…" />
              <button type="button" className="btn btn-ghost left" onClick={() => { setText(SAMPLE); if (!title) setTitle('Demo: launch announcement'); }}>
                Insert demo text with deliberate violations</button>
            </label>
          ) : (
            <label><span>File * (TXT, PDF, DOCX, PNG, JPG · max {MAX_MB} MB)</span>
              <input type="file" accept=".txt,.pdf,.docx,.png,.jpg,.jpeg" onChange={(e) => pick(e.target.files[0])} />
              <small className="muted">Text in images is read with OCR, which can make mistakes. Check the extracted text afterwards.</small>
            </label>
          )}
          <div className="row gap end">
            <button className="btn btn-primary" disabled={busy}>{busy ? 'Reading content…' : 'Create draft'}</button>
          </div>
        </form>
      </Card>
    </>
  );
}
