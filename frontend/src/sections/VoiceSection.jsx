import { AudioLines, Play, Trash2, Sparkles } from 'lucide-react'
import { SectionShell, GlassCard, EmptyState } from '../components/ui.jsx'
import { useApp } from '../state/AppContext.jsx'
import { usePersistedState } from '../state/store.js'

const SEED_VOICES = [
  { id: 'v_naira', name: 'Naira', desc: 'Naira OS default — RVC trained', model: 'naira.pth', builtin: true, active: true },
  { id: 'v_zen', name: 'Naira Zen', desc: 'Alternate RVC timbre', model: 'naira_zen.pth', builtin: true, active: false },
]

export default function VoiceSection({ onClose }) {
  const { toast } = useApp()
  const [voices, setVoices] = usePersistedState('naira.voices', SEED_VOICES)

  const selectVoice = (id) => {
    setVoices((list) => list.map((v) => ({ ...v, active: v.id === id })))
    const v = voices.find((x) => x.id === id)
    toast(`Active voice: ${v?.name || 'selected'}`, 'success')
  }

  const preview = (name) => {
    if (!('speechSynthesis' in window)) return
    const u = new SpeechSynthesisUtterance(`Hi, I'm ${name}. Naira voice library ready.`)
    u.lang = 'en-US'
    u.pitch = 1.15
    u.rate = 1
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(u)
  }

  return (
    <SectionShell icon={<AudioLines size={18} />} title="Voice" subtitle="RVC voice library" onClose={onClose}>
      <div className="card fade-up" style={{ background: 'linear-gradient(140deg, rgba(244,114,182,0.1), rgba(167,139,250,0.08))' }}>
        <div className="row" style={{ gap: 12 }}>
          <Sparkles size={18} style={{ color: 'var(--pink)' }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: 13.5 }}>RVC Voice Conversion</div>
            <div className="tiny" style={{ marginTop: 3, textTransform: 'none', letterSpacing: 0, lineHeight: 1.6 }}>
              Base TTS (EdgeTTS) → <b style={{ color: 'var(--text-2)' }}>.pth + .index</b> model se Naira ki awaaz. Abhi limited library — aage badhenge.
            </div>
          </div>
        </div>
      </div>

      <div className="tiny">{voices.length} voices in library</div>

      {voices.map((v) => (
        <GlassCard
          key={v.id}
          className="card"
          hover
          style={{ cursor: 'pointer', borderColor: v.active ? 'var(--accent-2)' : undefined, boxShadow: v.active ? '0 0 22px var(--accent-glow)' : undefined }}
          onClick={() => selectVoice(v.id)}
        >
          <div className="between">
            <div className="row" style={{ gap: 12 }}>
              <div
                style={{
                  width: 40, height: 40, borderRadius: 99,
                  display: 'grid', placeItems: 'center', flexShrink: 0,
                  background: v.active ? 'linear-gradient(120deg, var(--accent-1), var(--accent-2))' : 'rgba(255,255,255,0.06)',
                  color: v.active ? '#071021' : 'var(--text-2)',
                  boxShadow: v.active ? '0 6px 20px var(--accent-glow)' : 'none',
                }}
              >
                <AudioLines size={17} />
              </div>
              <div>
                <div className="row" style={{ gap: 8 }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>{v.name}</span>
                  {v.active && <span className="badge badge-pink" style={{ textTransform: 'none', letterSpacing: 0 }}>Active</span>}
                  {v.builtin && <span className="badge badge-gray" style={{ textTransform: 'none', letterSpacing: 0 }}>Built-in</span>}
                </div>
                <div className="tiny" style={{ marginTop: 3, textTransform: 'none', letterSpacing: 0 }}>{v.desc}</div>
                <div className="tiny" style={{ marginTop: 3, textTransform: 'none', letterSpacing: 0, fontFamily: 'monospace' }}>{v.model}</div>
              </div>
            </div>
            <div className="row" style={{ gap: 6 }}>
              <button className="btn btn-ghost btn-tiny" onClick={(e) => { e.stopPropagation(); preview(v.name) }} title="Preview">
                <Play size={12} />
              </button>
              {!v.builtin && (
                <button className="btn btn-ghost btn-tiny" onClick={(e) => { e.stopPropagation(); setVoices((list) => list.filter((x) => x.id !== v.id)) }}>
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          </div>
        </GlassCard>
      ))}

      {voices.length === 0 && (
        <EmptyState icon={<AudioLines size={30} />} title="Voice library khaali" note="Nayi trained RVC voice add karo — jaise hi library badegi, voices yahan update hongi." />
      )}

      <div className="tiny" style={{ textAlign: 'center', lineHeight: 1.7, padding: '0 10px' }}>
        Models path: <b style={{ color: 'var(--text-2)' }}>backend/modules/voice/rvc_model/</b> · Naira ki awaaz RVC inference se transform hoti hai.
      </div>
    </SectionShell>
  )
}
