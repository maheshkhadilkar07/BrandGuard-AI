import { useEffect } from 'react';

export const Spinner = ({ label = 'Loading…' }) => (
  <div className="center-pad"><div className="spinner" aria-hidden /><span className="muted">{label}</span></div>
);

export const Alert = ({ kind = 'error', children, onClose }) =>
  children ? (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <span>{children}</span>
      {onClose && <button className="alert-x" onClick={onClose} aria-label="Dismiss">×</button>}
    </div>
  ) : null;

export const Card = ({ title, actions, children, className = '' }) => (
  <section className={`card ${className}`}>
    {(title || actions) && (
      <header className="card-head">{title && <h3>{title}</h3>}<div className="row gap">{actions}</div></header>
    )}
    {children}
  </section>
);

export const PageHeader = ({ title, subtitle, actions }) => (
  <div className="page-head">
    <div><h1>{title}</h1>{subtitle && <p className="muted">{subtitle}</p>}</div>
    <div className="row gap">{actions}</div>
  </div>
);

export const Empty = ({ children }) => <div className="empty">{children}</div>;

export function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={onClose}>
      <div className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => e.stopPropagation()}>
        <header className="card-head"><h3>{title}</h3><button className="btn btn-ghost" onClick={onClose} aria-label="Close">×</button></header>
        {children}
      </div>
    </div>
  );
}

export const fmtDate = (s) => (s ? new Date(s).toLocaleString() : '—');
