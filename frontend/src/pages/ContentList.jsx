import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Card, Empty, PageHeader, Spinner, fmtDate } from '../components/UI';
import { SeverityBadge, StatusBadge, STATUS_LABEL } from '../components/Badges';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

export default function ContentList() {
  const { user } = useAuth();
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    setRows(null);
    api.get('/content' + (status ? `?status=${status}` : '')).then(setRows).catch((e) => setError(e.message));
  }, [status]);

  return (
    <>
      <PageHeader title={user.role === 'creator' ? 'My content' : 'Content history'} subtitle="Every submission, its latest analysis and its review status."
        actions={user.role === 'creator' && <Link className="btn btn-primary" to="/content/new">+ New content</Link>} />
      <Alert>{error}</Alert>
      <Card actions={<select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
        <option value="">All statuses</option>{Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}>
        {!rows ? <Spinner /> : rows.length === 0 ? <Empty>No content found.</Empty> : (
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Title</th>{user.role !== 'creator' && <th>Creator</th>}<th>Type</th><th>Status</th><th>Issues</th><th>Updated</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.id}><td><Link to={r.status === 'submitted' && user.role === 'reviewer' ? `/review/${r.id}` : `/content/${r.id}`}><strong>{r.title}</strong></Link></td>
                {user.role !== 'creator' && <td>{r.creator_name}</td>}
                <td>{r.source_type.toUpperCase()}</td><td><StatusBadge status={r.status} /></td>
                <td>{r.issue_count === 0 ? '0' : Object.entries(r.severity_counts).map(([s, n]) => <span key={s} style={{ marginRight: 6 }}><SeverityBadge severity={s} /> {n}</span>)}</td>
                <td>{fmtDate(r.updated_at)}</td></tr>))}</tbody></table></div>
        )}
      </Card>
    </>
  );
}
