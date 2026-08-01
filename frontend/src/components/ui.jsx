import { motion } from 'framer-motion'

export function GlassCard({ className = '', style, children, hover = true, ...rest }) {
  return (
    <div className={`${hover ? 'glass glass-hover' : 'glass'} ${className}`} style={style} {...rest}>
      {children}
    </div>
  )
}

export function Toggle({ checked, onChange, disabled }) {
  return (
    <button
      type="button"
      className={`toggle ${checked ? 'on' : ''}`}
      aria-pressed={checked}
      onClick={() => !disabled && onChange?.(!checked)}
    />
  )
}

export function Slider({ min = 0, max = 100, value, onChange, disabled }) {
  const fill = ((value - min) / (max - min)) * 100
  return (
    <input
      type="range"
      min={min}
      max={max}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange?.(Number(e.target.value))}
      style={{ '--fill': `${fill}%` }}
    />
  )
}

export function SectionShell({ icon, title, subtitle, onClose, children, accent }) {
  return (
    <motion.div
      className="section-panel"
      initial={{ x: 520, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 560, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 32 }}
    >
      <div className="section-head">
        <div className="section-head-icon" style={accent ? { background: accent.background, boxShadow: accent.shadow } : undefined}>
          {icon}
        </div>
        <div className="grow">
          <div className="section-title">{title}</div>
          {subtitle && <div className="tiny" style={{ marginTop: 2 }}>{subtitle}</div>}
        </div>
        <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose} title="Close">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div className="section-body">{children}</div>
    </motion.div>
  )
}

export function Modal({ open, onClose, title, children, danger }) {
  if (!open) return null
  return (
    <motion.div
      className="modal-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={(e) => e.target === e.currentTarget && onClose?.()}
    >
      <motion.div
        className="modal-card glass"
        initial={{ scale: 0.9, y: 16 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.92, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 340, damping: 28 }}
      >
        <div className="between">
          <div className="font-display" style={{ fontSize: 17, fontWeight: 700 }}>
            {title}
          </div>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        {children}
      </motion.div>
    </motion.div>
  )
}

export function EmptyState({ icon, title, note }) {
  return (
    <div className="glass-soft" style={{ padding: 30, textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' }}>
      <div style={{ color: 'var(--text-3)', opacity: 0.6 }}>{icon}</div>
      <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-2)' }}>{title}</div>
      {note && <div className="tiny" style={{ maxWidth: 260 }}>{note}</div>}
    </div>
  )
}

export function StatusPill({ label, value, tone = 'gray' }) {
  return (
    <div className="row">
      <span className="tiny" style={{ flex: 1 }}>{label}</span>
      <span className={`badge badge-${tone}`}>
        <span className="dot" />
        {value}
      </span>
    </div>
  )
}
