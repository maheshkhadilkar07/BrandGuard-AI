import { useState } from 'react';
import RuleManager from '../components/RuleManager';
import { PageHeader } from '../components/UI';
import { Pill, SeverityBadge } from '../components/Badges';

const SEV = ['Critical', 'High', 'Medium', 'Low'].map((s) => [s, s]);
const src = { name: 'source_reference', label: 'Source / reference' };

const facts = {
  title: 'Approved facts', noun: 'fact', path: '/facts',
  intro: 'Official prices, dates and details. If the value looks like a price (e.g. ₹999 per month) it is found automatically. For other facts add a pattern whose first bracket captures the value.',
  columns: [
    { label: 'Subject', render: (r) => <><strong>{r.subject}</strong><div className="muted small">{r.statement}</div></> },
    { label: 'Approved value', render: (r) => <code>{r.correct_value}</code> },
    { label: 'Valid until', render: (r) => r.valid_until || '—' },
    { label: 'Source', render: (r) => r.source_reference || '—' },
  ],
  blank: { subject: '', statement: '', correct_value: '', match_pattern: '', source_reference: '', valid_until: '', is_active: true },
  toForm: (r) => ({ ...r, match_pattern: r.match_pattern || '', source_reference: r.source_reference || '', valid_until: r.valid_until || '' }),
  toPayload: (f) => ({ subject: f.subject, statement: f.statement, correct_value: f.correct_value, match_pattern: f.match_pattern || null,
    source_reference: f.source_reference || null, valid_until: f.valid_until || null, is_active: f.is_active }),
  fields: [
    { name: 'subject', label: 'Subject', required: true }, { name: 'statement', label: 'Full statement', type: 'textarea', required: true },
    { name: 'correct_value', label: 'Approved value', required: true, help: 'e.g. ₹999 per month, 2021, 14' },
    { name: 'match_pattern', label: 'Detection pattern (optional regular expression)', help: 'Example: launched\\s+in\\s+(\\d{4}). Leave empty for prices.' },
    src, { name: 'valid_until', label: 'Valid until (optional)', type: 'date', help: 'After this date, uses of the fact are flagged as possibly outdated.' },
    { name: 'is_active', label: 'Active', type: 'checkbox' },
  ],
};

const terms = {
  title: 'Approved terminology', noun: 'term', path: '/terminology',
  intro: 'Official names and the incorrect variants that must not be used.',
  columns: [
    { label: 'Approved term', render: (r) => <strong>{r.approved_term}</strong> },
    { label: 'Incorrect variants', render: (r) => r.incorrect_variants.length ? r.incorrect_variants.map((v) => <Pill key={v} kind="bad">{v}</Pill>) : '—' },
    { label: 'Note', render: (r) => r.note || '—' },
    { label: 'Source', render: (r) => r.source_reference || '—' },
  ],
  blank: { approved_term: '', variants: '', note: '', source_reference: '', is_active: true },
  toForm: (r) => ({ ...r, variants: (r.incorrect_variants || []).join('\n'), note: r.note || '', source_reference: r.source_reference || '' }),
  toPayload: (f) => ({ approved_term: f.approved_term, incorrect_variants: f.variants.split('\n').map((s) => s.trim()).filter(Boolean),
    note: f.note || null, source_reference: f.source_reference || null, is_active: f.is_active }),
  fields: [
    { name: 'approved_term', label: 'Approved term', required: true },
    { name: 'variants', label: 'Incorrect variants (one per line)', type: 'textarea' },
    { name: 'note', label: 'Note' }, src, { name: 'is_active', label: 'Active', type: 'checkbox' },
  ],
};

const prohibited = {
  title: 'Prohibited words and phrases', noun: 'prohibited phrase', path: '/prohibited-words',
  intro: 'Phrases that must not appear. A phrase is allowed only if the same wording is registered as an approved claim.',
  columns: [
    { label: 'Phrase', render: (r) => <strong>“{r.phrase}”</strong> },
    { label: 'Suggested replacement', render: (r) => r.suggested_replacement || <span className="muted">none (rewrite manually)</span> },
    { label: 'Reason', render: (r) => r.reason || '—' },
    { label: 'Severity', render: (r) => <SeverityBadge severity={r.severity} /> },
  ],
  blank: { phrase: '', suggested_replacement: '', severity: 'High', reason: '', source_reference: '', is_active: true },
  toForm: (r) => ({ ...r, suggested_replacement: r.suggested_replacement || '', reason: r.reason || '', source_reference: r.source_reference || '' }),
  toPayload: (f) => ({ phrase: f.phrase, suggested_replacement: f.suggested_replacement || null, severity: f.severity,
    reason: f.reason || null, source_reference: f.source_reference || null, is_active: f.is_active }),
  fields: [
    { name: 'phrase', label: 'Phrase', required: true }, { name: 'suggested_replacement', label: 'Suggested replacement (optional)' },
    { name: 'severity', label: 'Severity', type: 'select', options: SEV }, { name: 'reason', label: 'Reason', type: 'textarea' },
    src, { name: 'is_active', label: 'Active', type: 'checkbox' },
  ],
};

const claims = {
  title: 'Promotional claims', noun: 'claim', path: '/claims',
  intro: '“Approved” claims (with evidence) may be used. “Requires evidence” claims are flagged for human verification whenever they appear.',
  columns: [
    { label: 'Claim', render: (r) => <strong>“{r.claim_text}”</strong> },
    { label: 'Status', render: (r) => <Pill kind={r.status === 'approved' ? 'good' : 'warn'}>{r.status === 'approved' ? 'Approved' : 'Requires evidence'}</Pill> },
    { label: 'Evidence', render: (r) => r.evidence || <span className="muted">none on file</span> },
    { label: 'Source', render: (r) => r.source_reference || '—' },
  ],
  blank: { claim_text: '', status: 'requires_evidence', evidence: '', source_reference: '', is_active: true },
  toForm: (r) => ({ ...r, evidence: r.evidence || '', source_reference: r.source_reference || '' }),
  toPayload: (f) => ({ claim_text: f.claim_text, status: f.status, evidence: f.evidence || null, source_reference: f.source_reference || null, is_active: f.is_active }),
  fields: [
    { name: 'claim_text', label: 'Claim wording', required: true },
    { name: 'status', label: 'Status', type: 'select', options: [['requires_evidence', 'Requires evidence'], ['approved', 'Approved']] },
    { name: 'evidence', label: 'Evidence', type: 'textarea', help: 'Required when the claim is approved.' },
    src, { name: 'is_active', label: 'Active', type: 'checkbox' },
  ],
};

const TABS = [['facts', 'Approved facts', facts], ['terms', 'Terminology', terms], ['prohibited', 'Prohibited words', prohibited], ['claims', 'Promotional claims', claims]];

export default function FactsTerms() {
  const [tab, setTab] = useState('facts');
  const current = TABS.find((t) => t[0] === tab)[2];
  return (
    <>
      <PageHeader title="Facts & Terminology" subtitle="Approved facts, terminology, prohibited words and promotional claims." />
      <div className="tabs" role="tablist">
        {TABS.map(([k, label]) => <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? 'active' : ''}`} onClick={() => setTab(k)}>{label}</button>)}
      </div>
      <RuleManager key={tab} config={current} />
    </>
  );
}
