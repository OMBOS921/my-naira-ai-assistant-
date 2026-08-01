import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronLeft, ChevronRight, Sparkles, User, Heart, Cpu } from 'lucide-react'
import { useApp } from '../state/AppContext.jsx'
import AvatarStage from '../components/AvatarStage.jsx'
import Background3D from '../components/Background3D.jsx'

const STEPS = [
  { key: 'basic', icon: User, title: 'About You', note: 'Naira ko batao aap kaun ho' },
  { key: 'prefs', icon: Heart, title: 'Preferences', note: 'Naira kaise behave kare' },
  { key: 'system', icon: Cpu, title: 'System Context', note: 'Aapke PC ki baatein' },
]

const LANGUAGES = [
  { value: 'hinglish', label: 'Hinglish (हिंग्लिश)', hint: 'Hindi + English mix' },
  { value: 'hindi', label: 'Hindi (हिंदी)' },
  { value: 'english', label: 'English' },
]

const TONES = [
  { value: 'friendly', label: 'Friendly', emoji: '🌸', hint: 'Warm aur pyara' },
  { value: 'professional', label: 'Professional', emoji: '💼', hint: 'Short aur precise' },
  { value: 'playful', label: 'Playful', emoji: '✨', hint: 'Fun + jokes' },
]

export default function HandshakeScreen() {
  const { setScreen, setProfile, toast, send } = useApp()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    name: '',
    language: 'hinglish',
    tone: 'friendly',
    wakeWord: 'Hey Naira',
    pcName: '',
    timezone: '',
    role: '',
  })

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target ? e.target.value : e }))
  const valid = step === 0 ? form.name.trim().length >= 2 : true

  const finish = () => {
    const profile = {
      ...form,
      name: form.name.trim(),
      createdAt: Date.now(),
      complete: true,
    }
    setProfile(profile)
    toast('Identity sealed — aap dobara kabhi yeh screen nahi dekhenge', 'success')
    send({ type: 'system_init', name: profile.name, session_id: 'default' })
    setTimeout(() => setScreen('dashboard'), 700)
  }

  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 2, display: 'grid', placeItems: 'center', padding: 24 }}>
      <Background3D />
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', maxWidth: 900 }}>
        <motion.div
          className="glass"
          style={{ width: '100%', padding: '30px 34px', display: 'flex', flexDirection: 'column', gap: 22 }}
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="between">
            <div className="row" style={{ gap: 14 }}>
              <AvatarStage size="sm" state="custom" />
              <div>
                <div className="font-display" style={{ fontSize: 18, fontWeight: 700 }}>
                  Operator <span className="grad-text">Handshake</span>
                </div>
                <div className="muted" style={{ fontSize: 12.5, marginTop: 3 }}>
                  Ek baar complete — hamesha ke liye sealed
                </div>
              </div>
            </div>
            <div className="row" style={{ gap: 8 }}>
              {STEPS.map((s, i) => (
                <div
                  key={s.key}
                  style={{
                    width: 42, height: 42, borderRadius: 13, display: 'grid', placeItems: 'center',
                    background: i <= step ? 'linear-gradient(120deg, var(--accent-1), var(--accent-2))' : 'var(--surface-2)',
                    color: i <= step ? '#071021' : 'var(--text-3)',
                    border: i > step ? '1px solid var(--stroke)' : 'none',
                    boxShadow: i <= step ? '0 6px 20px var(--accent-glow)' : 'none',
                    transition: 'all 0.35s',
                  }}
                  title={s.title}
                >
                  <s.icon size={17} />
                </div>
              ))}
            </div>
          </div>

          <div className="progress-track">
            <div className="progress-bar" style={{ width: `${((step + 1) / 3) * 100}%` }} />
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 34 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -34 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              style={{ minHeight: 250, display: 'flex', flexDirection: 'column' }}
            >
              {step === 0 && (
                <>
                  <div className="field-group">
                    <label className="field-label">Operator Name *</label>
                    <input className="field" placeholder="Aapka naam kya hai?" value={form.name} onChange={set('name')} autoFocus />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Preferred Language</label>
                    <div className="grid-2">
                      {LANGUAGES.map((l) => (
                        <button
                          key={l.value}
                          type="button"
                          className="card glass-hover"
                          style={{
                            textAlign: 'left', cursor: 'pointer', padding: 14,
                            borderColor: form.language === l.value ? 'var(--accent-1)' : undefined,
                            boxShadow: form.language === l.value ? '0 0 20px var(--accent-glow)' : undefined,
                          }}
                          onClick={() => setForm((f) => ({ ...f, language: l.value }))}
                        >
                          <div style={{ fontWeight: 700, fontSize: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Sparkles size={13} style={{ color: form.language === l.value ? 'var(--accent-1)' : 'var(--text-3)' }} />
                            {l.label}
                          </div>
                          {l.hint && <div className="tiny" style={{ marginTop: 5, textTransform: 'none', letterSpacing: 0 }}>{l.hint}</div>}
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {step === 1 && (
                <>
                  <div className="field-group">
                    <label className="field-label">Naira's Tone</label>
                    <div className="grid-2">
                      {TONES.map((t) => (
                        <button
                          key={t.value}
                          type="button"
                          className="card glass-hover"
                          style={{
                            textAlign: 'left', cursor: 'pointer', padding: 14,
                            borderColor: form.tone === t.value ? 'var(--accent-1)' : undefined,
                            boxShadow: form.tone === t.value ? '0 0 20px var(--accent-glow)' : undefined,
                          }}
                          onClick={() => setForm((f) => ({ ...f, tone: t.value }))}
                        >
                          <div style={{ fontWeight: 700, fontSize: 14 }}>{t.emoji} {t.label}</div>
                          {t.hint && <div className="tiny" style={{ marginTop: 5, textTransform: 'none', letterSpacing: 0 }}>{t.hint}</div>}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="field-group">
                    <label className="field-label">Wake Word</label>
                    <input className="field" placeholder="Hey Naira" value={form.wakeWord} onChange={set('wakeWord')} />
                    <div className="tiny" style={{ marginTop: 7, textTransform: 'none', letterSpacing: 0 }}>
                      Isse bolo to Naira turant sunne lagegi
                    </div>
                  </div>
                </>
              )}

              {step === 2 && (
                <>
                  <div className="grid-2">
                    <div className="field-group">
                      <label className="field-label">PC Name</label>
                      <input className="field" placeholder="e.g. DESKTOP-7X" value={form.pcName} onChange={set('pcName')} />
                    </div>
                    <div className="field-group">
                      <label className="field-label">Timezone</label>
                      <input className="field" placeholder="Asia/Kolkata" value={form.timezone} onChange={set('timezone')} />
                    </div>
                  </div>
                  <div className="field-group">
                    <label className="field-label">Your Role</label>
                    <select className="field" value={form.role} onChange={set('role')}>
                      <option value="">Select...</option>
                      <option value="student">Student</option>
                      <option value="developer">Developer</option>
                      <option value="creator">Creator</option>
                      <option value="gamer">Gamer</option>
                      <option value="professional">Professional</option>
                      <option value="other">Other</option>
                    </select>
                    <div className="tiny" style={{ marginTop: 7, textTransform: 'none', letterSpacing: 0 }}>
                      Isse Naira aapke kaam ka context samajhti hai
                    </div>
                  </div>
                </>
              )}
            </motion.div>
          </AnimatePresence>

          <div className="between">
            <button className="btn btn-ghost" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
              <ChevronLeft size={16} /> Back
            </button>
            {step < 2 ? (
              <button className="btn btn-primary" disabled={!valid} onClick={() => setStep((s) => s + 1)}>
                Continue <ChevronRight size={16} />
              </button>
            ) : (
              <button className="btn btn-primary" onClick={finish}>
                <Sparkles size={16} /> Seal Identity
              </button>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  )
}
