import { ArcElement, BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

export const SEV_COLORS = { Critical: '#b42318', High: '#e8590c', Medium: '#d9a400', Low: '#2f80ed' };

export function SeverityChart({ data }) {
  const labels = Object.keys(data);
  const total = labels.reduce((a, k) => a + data[k], 0);
  if (!total) return <p className="muted">No issues recorded yet.</p>;
  return (
    <div className="chart-box">
      <Doughnut data={{ labels, datasets: [{ data: labels.map((l) => data[l]), backgroundColor: labels.map((l) => SEV_COLORS[l]) }] }}
        options={{ plugins: { legend: { position: 'bottom' } }, maintainAspectRatio: false }} />
    </div>
  );
}

export function BarChart({ labels, values, color = '#4f46e5', horizontal = false, label = 'Count' }) {
  if (!labels.length) return <p className="muted">No data yet.</p>;
  return (
    <div className="chart-box">
      <Bar data={{ labels, datasets: [{ label, data: values, backgroundColor: color, borderRadius: 4 }] }}
        options={{ indexAxis: horizontal ? 'y' : 'x', plugins: { legend: { display: false } }, maintainAspectRatio: false,
          scales: { [horizontal ? 'x' : 'y']: { beginAtZero: true, ticks: { precision: 0 } } } }} />
    </div>
  );
}
