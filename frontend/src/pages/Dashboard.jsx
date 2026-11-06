import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Card, Empty, PageHeader, Spinner, fmtDate } from '../components/UI';
import { BarChart, SeverityChart } from '../components/Charts';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

const Stat = ({ label, value, tone, to }) => {
  const body = <div className={`stat ${tone || ''}`}><div className="stat-val">{value}</div><div className="stat-label">{label}</div></div>;
  return to ? <Link to={to} className="stat-link">{body}</Link> : body;
};

const ACTION_TEXT = (a) => a.replace(/\./g, ' › ').replace(/_/g, ' ');

export default function Dashboard() {
  const { user } = useAuth();
  const [d, setD] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { api.get('/dashboard').then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Alert>{error}</Alert>;
  if (!d) return <Spinner />;

  const titles = {
    admin: ['Admin dashboard', 'Organisation-wide view of rules, content and compliance.'],
    creator: ['Creator dashboard', 'Your content and its compliance status.'],
    reviewer: ['Reviewer dashboard', 'Content waiting for your decision.'],
  }[user.role];

  return (
    <>
      <PageHeader title={titles[0]} subtitle={titles[1]}
        actions={user.role === 'creator' ? <Link className="btn btn-primary" to="/content/new">+ New content</Link>
          : user.role === 'reviewer' ? <Link className="btn btn-primary" to="/review">Open review queue</Link> : null} />
      <div className="stats">
        <Stat label={user.role === 'creator' ? 'My submissions' : 'Total submissions'} value={d.total_submissions} to="/content" />
        <Stat label="Awaiting review" value={d.awaiting_review} tone="warn" to={user.role === 'creator' ? '/content' : '/review'} />
        <Stat label="Approved" value={d.approved} tone="good" />
        <Stat label="Rejected" value={d.rejected} tone="bad" />
        {user.role === 'creator' && <Stat label="Changes requested" value={d.changes_requested} tone="warn" />}
        <Stat label="Compliance issues" value={d.total_issues} />
        {user.role === 'admin' && <Stat label="Users" value={d.users} to="/users" />}
        {user.role === 'reviewer' && <Stat label="My decisions" value={d.my_decisions} />}
      </div>

      <div className="grid-2">
        <Card title="Issues by severity"><SeverityChart data={d.issues_by_severity} /></Card>
        <Card title="Most common violation categories">
          <BarChart labels={d.issues_by_category.map((c) => c.category)} values={d.issues_by_category.map((c) => c.count)} horizontal />
        </Card>
      </div>
      <div className="grid-2">
        <Card title="Content by status">
          <BarChart labels={Object.keys(d.by_status).map((s) => s.replace('_', ' '))} values={Object.values(d.by_status)} color="#0e9f6e" />
        </Card>
        <Card title="Recent activity">
          {d.recent_activity.length === 0 ? <Empty>No activity yet.</Empty> : (
            <ul className="activity">
              {d.recent_activity.map((a) => (
                <li key={a.id}><strong>{ACTION_TEXT(a.action)}</strong>{a.user ? ` · ${a.user}` : ''}
                  {a.details ? <span className="muted"> — {a.details}</span> : null}
                  <div className="muted small">{fmtDate(a.created_at)}</div></li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      {user.role === 'admin' && d.rule_counts && (
        <Card title="Brand rules in this organisation">
          <div className="row wrap gap">
            {Object.entries(d.rule_counts).map(([k, v]) => <span key={k} className="pill pill-neutral">{k.replace('_', ' ')}: {v}</span>)}
          </div>
        </Card>
      )}
    </>
  );
}
