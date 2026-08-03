import { useEffect, useState, useCallback, useRef } from 'react'
import { AudioLines, Play, Loader2, RefreshCw, AlertTriangle, Sparkles, CheckCircle2 } from 'lucide-react'
import { SectionShell, GlassCard, EmptyState } from '../components/ui.jsx'
import { useApp } from '../state/AppContext.jsx'
import { getVoiceProviders, setActiveVoiceProvider, previewVoice } from '../api/client.js'

export default function VoiceSection({ onClose }) {
  const { toast } = useApp()
  const [providers, setProviders] = useState([])
  const [loading, setLoading] = useState(true)
  const [previewing, setPreviewing] = useState(null)
  const audioRef = useRef(null)

  const loadProviders = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getVoiceProviders()
      if (res && Array.isArray(res.providers)) setProviders(res.providers)
    } catch (err) {
      toast(err.message || 'Voice providers load nahi hui', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    loadProviders()
  }, [loadProviders])

  const selectProvider = async (name) => {
    // Optimistic update
    const prev = providers.map((p) => ({ ...p, active: p.name === name }))
    const rollback = [...providers]
    setProviders(prev)
    try {
      await setActiveVoiceProvider(name)
      const p = providers.find((x) => x.name === name)
      toast(`Active voice: ${p?.provider_name || name}`, 'success')
    } catch (err) {
      setProviders(rollback)
      toast(err.message || 'Provider switch fail ho gaya', 'error')
    }
  }

  const handlePreview = async (providerName) => {
    setPreviewing(providerName)
    try {
      const res = await previewVoice()
      if (res && res.audio) {
        const format = res.format || 'mp3'
        const audio = new Audio(`data:audio/${format};base64,${res.audio}`)
        audioRef.current?.pause()
        audioRef.current = audio
        audio.play().catch(() => toast('Audio play failed', 'error'))
        audio.onended = () => setPreviewing(null)
      } else {
        toast('Preview audio nahi mila — TTS available nahi hai?', 'error')
        setPreviewing(null)
      }
    } catch (err) {
      toast(err.message || 'Preview fail ho gaya', 'error')
      setPreviewing(null)
    }
  }

  return (
    <SectionShell icon={<AudioLines size={18} />} title="Voice" subtitle="RVC voice library" onClose={onClose}>
      <div className="card fade-up" style={{ background: 'linear-gradient(140deg, rgba(244,114,182,0.1), rgba(167,139,250,0.08))' }}>
        <div className="row" style={{ gap: 12 }}>
          <Sparkles size={18} style={{ color: 'var(--pink)' }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: 13.5 }}>RVC Voice Conversion</div>
            <div className="tiny" style={{ marginTop: 3, textTransform: 'none', letterSpacing: 0, lineHeight: 1.6 }}>
              Base TTS (EdgeTTS) → <b style={{ color: 'var(--text-2)' }}>.pth + .index</b> model se Naira ki awaaz. Voice providers backend se load hote hain.
            </div>
          </div>
        </div>
      </div>

      <div className="between" style={{ marginBottom: -4 }}>
        <div className="tiny">{providers.length} provider{providers.length !== 1 ? 's' : ''} registered</div>
        <button className="btn btn-ghost btn-tiny" onClick={loadProviders} disabled={loading} title="Refresh">
          <Loader2 size={12} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="glass-soft" style={{ padding: 24, textAlign: 'center' }}>
          <Loader2 size={20} className="spin" style={{ color: 'var(--accent-1)' }} />
        </div>
      ) : providers.length === 0 ? (
        <EmptyState
          icon={<AudioLines size={30} />}
          title="Koi TTS provider nahi mila"
          note="Backend offline hai ya koi TTS provider register nahi hua. edge-tts install karo aur restart karo."
        />
      ) : (
        providers.map((p) => {
          const isUnavailable = !p.is_available
          return (
            <GlassCard
              key={p.name}
              className="card"
              hover={!isUnavailable}
              style={{
                cursor: isUnavailable ? 'not-allowed' : 'pointer',
                opacity: isUnavailable ? 0.55 : 1,
                borderColor: p.active ? 'var(--accent-2)' : undefined,
                boxShadow: p.active ? '0 0 22px var(--accent-glow)' : undefined,
              }}
              onClick={() => !isUnavailable && selectProvider(p.name)}
            >
              <div className="between">
                <div className="row" style={{ gap: 12 }}>
                  <div
                    style={{
                      width: 40, height: 40, borderRadius: 99,
                      display: 'grid', placeItems: 'center', flexShrink: 0,
                      background: p.active
                        ? 'linear-gradient(120deg, var(--accent-1), var(--accent-2))'
                        : isUnavailable
                          ? 'rgba(239,68,68,0.13)'
                          : 'rgba(255,255,255,0.06)',
                      color: p.active ? '#071021' : isUnavailable ? '#ef4444' : 'var(--text-2)',
                      boxShadow: p.active ? '0 6px 20px var(--accent-glow)' : 'none',
                    }}
                  >
                    {isUnavailable ? <AlertTriangle size={17} /> : <AudioLines size={17} />}
                  </div>
                  <div>
                    <div className="row" style={{ gap: 8 }}>
                      <span style={{ fontWeight: 700, fontSize: 14 }}>{p.provider_name || p.name}</span>
                      {p.active && (
                        <span className="badge badge-pink" style={{ textTransform: 'none', letterSpacing: 0 }}>
                          <CheckCircle2 size={10} style={{ marginRight: 3 }} /> Active
                        </span>
                      )}
                    </div>
                    <div className="tiny" style={{ marginTop: 3, textTransform: 'none', letterSpacing: 0 }}>
                      {isUnavailable
                        ? 'Unavailable — dependency missing (pip install required)'
                        : `Registered as "${p.name}"`}
                    </div>
                  </div>
                </div>
                <div className="row" style={{ gap: 6 }}>
                  <button
                    className="btn btn-ghost btn-tiny"
                    disabled={isUnavailable || previewing !== null}
                    onClick={(e) => {
                      e.stopPropagation()
                      handlePreview(p.name)
                    }}
                    title="Preview voice"
                  >
                    {previewing === p.name ? (
                      <Loader2 size={12} className="spin" />
                    ) : (
                      <Play size={12} />
                    )}
                  </button>
                </div>
              </div>
            </GlassCard>
          )
        })
      )}

      <div className="tiny" style={{ textAlign: 'center', lineHeight: 1.7, padding: '0 10px' }}>
        Models path: <b style={{ color: 'var(--text-2)' }}>backend/modules/voice/rvc_model/</b> · Naira ki awaaz RVC inference se transform hoti hai.
      </div>
    </SectionShell>
  )
}
