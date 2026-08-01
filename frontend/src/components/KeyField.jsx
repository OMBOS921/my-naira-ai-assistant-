import { useState } from 'react'
import { Eye, EyeOff, ArrowUpRight, KeyRound, ShieldCheck, ShieldAlert, CircleDot } from 'lucide-react'

const BADGES = {
  set: { label: 'Set', cls: 'badge-mint', icon: ShieldCheck },
  required: { label: 'Required', cls: 'badge-amber', icon: ShieldAlert },
  optional: { label: 'Optional', cls: 'badge-gray', icon: CircleDot },
}

export default function KeyField({ label, dot, placeholder, value, onChange, status = 'optional', helper, getKeyLink, onGetKey }) {
  const [visible, setVisible] = useState(false)
  const badge = BADGES[status] || BADGES.optional
  const BadgeIcon = badge.icon

  return (
    <div className="field-group fade-up">
      <div className="between" style={{ marginBottom: 8 }}>
        <label className="field-label" style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: 99, background: 'var(--accent-1)', boxShadow: '0 0 8px var(--accent-glow)' }} />
          {label}
        </label>
        <span className={`badge ${badge.cls}`} style={{ textTransform: 'none', letterSpacing: 0 }}>
          <BadgeIcon size={11} />
          {badge.label}
        </span>
      </div>

      <div style={{ position: 'relative' }}>
        <KeyRound size={15} style={{ position: 'absolute', left: 13, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-3)', zIndex: 1 }} />
        <input
          className="field"
          type={visible ? 'text' : 'password'}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          style={{ paddingLeft: 38, paddingRight: 88 }}
        />
        <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 4 }}>
          <button
            type="button"
            className="btn btn-ghost btn-tiny"
            style={{ padding: '5px 7px' }}
            onClick={() => setVisible((v) => !v)}
            title={visible ? 'Hide key' : 'Show key'}
          >
            {visible ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
          {getKeyLink && (
            <button
              type="button"
              className="btn btn-ghost btn-tiny"
              style={{ padding: '5px 8px' }}
              onClick={() => (onGetKey ? onGetKey() : window.open(getKeyLink, '_blank'))}
              title="Get key"
            >
              <ArrowUpRight size={14} />
            </button>
          )}
        </div>
      </div>
      {helper && <div className="tiny" style={{ marginTop: 7, textTransform: 'none', letterSpacing: 0 }}>{helper}</div>}
    </div>
  )
}
