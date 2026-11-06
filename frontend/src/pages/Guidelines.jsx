import RuleManager from '../components/RuleManager';
import { PageHeader } from '../components/UI';
import { SeverityBadge } from '../components/Badges';

const CATEGORIES = [
  ['brand_voice', 'Brand voice (tone)'], ['writing', 'Writing / readability'], ['claims', 'Promotional claims policy'],
  ['required_info', 'Required information'], ['accessibility', 'Accessibility'], ['terminology', 'Terminology'], ['general', 'General'],
];
const SEVERITIES = ['Critical', 'High', 'Medium', 'Low'].map((s) => [s, s]);

const config = {
  title: 'Brand guidelines', noun: 'guideline', path: '/guidelines',
  intro: 'Written brand rules. Tone, claims, readability, accessibility and required-wording guidelines are used by the compliance engine and cited in findings.',
  columns: [
    { label: 'Category', render: (r) => CATEGORIES.find((c) => c[0] === r.category)?.[1] || r.category },
    { label: 'Title & description', render: (r) => <><strong>{r.title}</strong><div className="muted small">{r.description}</div></> },
    { label: 'Source', render: (r) => r.source_reference || '—' },
    { label: 'Severity', render: (r) => <SeverityBadge severity={r.severity} /> },
  ],
  blank: { category: 'brand_voice', title: '', description: '', source_reference: '', severity: 'Medium', required_phrases: '', applies_if_contains: '', is_active: true },
  toForm: (r) => ({ ...r, source_reference: r.source_reference || '',
    required_phrases: (r.params?.required_phrases || []).join('\n'), applies_if_contains: r.params?.applies_if_contains || '' }),
  toPayload: (f) => {
    const p = { category: f.category, title: f.title, description: f.description, source_reference: f.source_reference || null,
      severity: f.severity, is_active: f.is_active, params: null };
    if (f.category === 'required_info') {
      p.params = { required_phrases: f.required_phrases.split('\n').map((s) => s.trim()).filter(Boolean) };
      if (f.applies_if_contains.trim()) p.params.applies_if_contains = f.applies_if_contains.trim();
    }
    return p;
  },
  fields: [
    { name: 'category', label: 'Category', type: 'select', options: CATEGORIES, required: true },
    { name: 'title', label: 'Title', required: true },
    { name: 'description', label: 'Description', type: 'textarea', required: true },
    { name: 'source_reference', label: 'Source / reference', help: 'Where this rule comes from (e.g. Brand Book §2).' },
    { name: 'severity', label: 'Default severity', type: 'select', options: SEVERITIES },
    { name: 'required_phrases', label: 'Required phrases (one per line)', type: 'textarea', show: (f) => f.category === 'required_info', required: true },
    { name: 'applies_if_contains', label: 'Only applies if the content contains', show: (f) => f.category === 'required_info', help: 'Optional, e.g. ₹ to apply only to content that mentions prices.' },
    { name: 'is_active', label: 'Active', type: 'checkbox' },
  ],
};

export default function Guidelines() {
  return (<><PageHeader title="Brand Guidelines" subtitle="Brand voice, writing instructions and policies." /><RuleManager config={config} /></>);
}
