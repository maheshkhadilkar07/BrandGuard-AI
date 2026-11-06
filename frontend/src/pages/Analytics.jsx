import { useEffect, useState } from 'react';
import { Alert, Card, PageHeader, Spinner } from '../components/UI';
import { BarChart, SeverityChart } from '../components/Charts';
import { api } from '../services/api';

export default function Analytics() {
  const [d, setD] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { api.get('/analytics').then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Alert>{error}</Alert>;
  if (!d) return <Spinner />;
  const sev = Object.fromEntries(['Critical', 'High', 'Medium', 'Low'].map((s) => [s, d.issues_by_severity.find((x) => x.severity === s)?.count || 0]));
  return (
    <>
      <PageHeader title="Analytics" subtitle="Patterns across content in your organisation. Based only on data stored in this system." />
      <div className="grid-2">
        <Card title="Issues by severity"><SeverityChart data={sev} /></Card>
        <Card title="Issues by category"><BarChart labels={d.issues_by_category.map((x) => x.category)} values={d.issues_by_category.map((x) => x.count)} horizontal /></Card>
      </div>
      <div className="grid-2">
        <Card title="Most frequently violated rules">
          <BarChart labels={d.most_violated_rules.map((x) => x.rule.slice(0, 40))} values={d.most_violated_rules.map((x) => x.count)} horizontal color="#e8590c" />
          <p className="muted small">Rules that are broken often may need clearer wording or training.</p>
        </Card>
        <Card title="Submissions per day (last 14 days)"><BarChart labels={d.submissions_per_day.map((x) => x.date)} values={d.submissions_per_day.map((x) => x.count)} color="#0e9f6e" /></Card>
      </div>
      <Card title="Reviewer decisions">
        <BarChart labels={['Approved', 'Changes requested', 'Rejected']} values={[d.review_decisions.approved, d.review_decisions.changes_requested, d.review_decisions.rejected]} color="#4f46e5" />
      </Card>
    </>
  );
}
