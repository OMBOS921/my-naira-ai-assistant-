import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Settings, KeyRound, ShieldCheck, Loader2, Upload, AudioLines, Palette, Check, X, Mic } from 'lucide-react'
import { GlassCard, Toggle } from '../components/ui.jsx'
import { useApp, ACCENTS } from '../state/AppContext.jsx'
import { getVaultStatus, saveVaultConfiguration } from '../api/client.js'
import KeyField from '../components/KeyField.jsx'
import { usePersistedState, makeId } from '../state/store.js'

export default function SettingsSection({ onClose, accent }) {
  const { toast, setAccent } = useApp()
  const [vault, setVault] = useState(null)
  const [provider, setProvider] = useState('gemini')
  const [apiKey, setApiKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [voices, setVoices] = usePersistedState('naira.voices', [])
  const [uploadName, setUploadName] = useState('')
  const [offlineStt, setOfflineStt] = usePersistedState('naira.settings.offlineStt', false)

  useEffect(() => {
    getVaultStatus().then((s) => {
      setVault(s)
      if (s.provider) setProvider(s.provider)
    })
  }, [])

  const updateVault = async () => {
    if (!apiKey.trim()) {
      toast('Naya API key paste karo pehle', 'error')
      return
    }
    setBusy(true)
    try {
      await saveVaultConfiguration({ provider, apiKey: apiKey.trim() })
      setApiKey('')
      const s = await getVaultStatus()
      setVault(s)
      toast('Key updated — vault hot-reload ho gaya, restart nahi chahiye', 'success')
    } catch (err) {
      toast(err.message || 'Key update failed', 'error')
    } finally {
      setBusy(false)
    }
  }

  const handleVoiceUpload = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const name = uploadName.trim() || file.name.replace(/\.(pth|index|zip)$/i, '')
    setVoices((list) => [
      ...list,
      {
        id: makeId('v'),
        name,
        desc: 'Settings se upload kiya gaya RVC model',
        model: file.name,
        builtin: false,
        active: false,
      },
    ])
    setUploadName('')
    toast(`Voice "${name}" library mein add ho gayi — Voice section se select karo`, 'success')
    e.target.value = ''
  }

  return (
    <motion.div
      className="modal-overlay"
      style={{ zIndex: 200 }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        className="glass no-scrollbar"
        style={{ width: 'min(850px, 92vw)', maxHeight: '85vh', overflowY: 'auto', padding: '32px', display: 'flex', flexDirection: 'column', gap: '20px' }}
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
      >
        {/* ---------- Header ---------- */}
        <div className="between">
          <div className="row" style={{ gap: 14 }}>
            <div className="section-head-icon">
              <Settings size={18} />
            </div>
            <div>
              <div className="font-display" style={{ fontSize: 19, fontWeight: 700 }}>Settings</div>
              <div className="tiny" style={{ marginTop: 3, textTransform: 'none', letterSpacing: 0 }}>System ke controls</div>
            </div>
          </div>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose} title="Close">
            <X size={17} />
          </button>
        </div>

        {/* ---------- API Key update ---------- */}
      <GlassCard className="card">
        <div className="card-title"><KeyRound size={14} /> API Key Update</div>
        <div className="row" style={{ marginBottom: 14 }}>
          <span className="badge badge-violet" style={{ textTransform: 'none', letterSpacing: 0 }}>
            Active: {vault?.provider === 'gemini' ? 'Gemini' : vault?.provider === 'deepseek' ? 'DeepSeek (Zen)' : '—'}
          </span>
          {vault?.configured && (
            <span className="badge badge-mint" style={{ textTransform: 'none', letterSpacing: 0 }}>
              <ShieldCheck size={11} /> Sealed
            </span>
          )}
        </div>
        <div className="field-group">
          <label className="field-label">Provider</label>
          <div className="grid-2">
            <button
              type="button"
              className="card glass-hover"
              style={{
                textAlign: 'center', cursor: 'pointer', padding: 10, fontSize: 13, fontWeight: 700,
                borderColor: provider === 'gemini' ? 'var(--accent-1)' : undefined,
                boxShadow: provider === 'gemini' ? '0 0 16px var(--accent-glow)' : undefined,
              }}
              onClick={() => setProvider('gemini')}
            >
              Gemini
            </button>
            <button
              type="button"
              className="card glass-hover"
              style={{
                textAlign: 'center', cursor: 'pointer', padding: 10, fontSize: 13, fontWeight: 700,
                borderColor: provider === 'deepseek' ? 'var(--accent-1)' : undefined,
                boxShadow: provider === 'deepseek' ? '0 0 16px var(--accent-glow)' : undefined,
              }}
              onClick={() => setProvider('deepseek')}
            >
              DeepSeek (Zen)
            </button>
          </div>
        </div>
        <KeyField
          label={provider === 'gemini' ? 'Naya Gemini API Key' : 'Naya OpenCode Zen API Key'}
          placeholder={provider === 'gemini' ? 'AIzaSy...' : 'zen-...'}
          value={apiKey}
          onChange={setApiKey}
          status={apiKey ? 'set' : 'optional'}
          helper="Verify hote hi memory/user_vault.json mein auto-save — hot reload, restart nahi"
          getKeyLink={provider === 'gemini' ? 'https://aistudio.google.com/apikey' : 'https://opencode.ai/zen'}
        />
        <button className="btn btn-primary btn-sm" style={{ width: '100%' }} disabled={busy} onClick={updateVault}>
          {busy ? <Loader2 size={15} className="spin" /> : <ShieldCheck size={15} />}
          {busy ? 'Verifying & sealing...' : 'Update & Seal'}
        </button>
      </GlassCard>

      {/* ---------- RVC voice upload ---------- */}
      <GlassCard className="card">
        <div className="card-title"><AudioLines size={14} /> RVC Trained Voice</div>
        <div className="row" style={{ gap: 12, marginBottom: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 11, display: 'grid', placeItems: 'center', background: 'rgba(244,114,182,0.13)', color: 'var(--pink)', flexShrink: 0 }}>
            <AudioLines size={16} />
          </div>
          <div className="tiny" style={{ textTransform: 'none', letterSpacing: 0, lineHeight: 1.6 }}>
            Voice section se connected — yahan upload karo, wahan select karo. ({voices.filter((v) => v.active).length || 1} active voice)
          </div>
        </div>
        <input
          className="field"
          placeholder="Voice name (optional)"
          value={uploadName}
          onChange={(e) => setUploadName(e.target.value)}
          style={{ marginBottom: 10 }}
        />
        <label className="btn btn-ghost btn-sm" style={{ width: '100%', cursor: 'pointer' }}>
          <Upload size={14} /> Upload .pth / .index model
          <input
            type="file"
            accept=".pth,.index,.zip,.onnx"
            style={{ display: 'none' }}
            onChange={handleVoiceUpload}
          />
        </label>
        <div className="tiny" style={{ marginTop: 10, textTransform: 'none', letterSpacing: 0 }}>
          Model path: <b style={{ color: 'var(--text-2)' }}>backend/modules/voice/rvc_model/</b>
        </div>
      </GlassCard>

      {/* ---------- Offline STT toggle ---------- */}
      <GlassCard className="card">
        <div className="card-title"><Mic size={14} /> Voice Recognition</div>
        <div className="between" style={{ alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>Use offline voice recognition (faster-whisper)</div>
            <div className="tiny" style={{ marginTop: 4, textTransform: 'none', letterSpacing: 0, lineHeight: 1.6 }}>
              Browser STT ke bajaye backend ka faster-whisper STT use karo. Internet nahi chahiye, lekin backend pe model loaded hona chahiye.
            </div>
          </div>
          <Toggle checked={offlineStt} onChange={(v) => {
            setOfflineStt(v)
            toast(v ? 'Offline STT enabled — backend faster-whisper' : 'Browser STT restored', v ? 'success' : 'info')
          }} />
        </div>
      </GlassCard>

      {/* ---------- Appearance ---------- */}
      <GlassCard className="card">
        <div className="card-title"><Palette size={14} /> Appearance</div>
        <div className="row" style={{ flexWrap: 'wrap', gap: 10 }}>
          {Object.entries(ACCENTS).map(([key, vars]) => {
            const active = accent === key
            return (
              <button
                key={key}
                type="button"
                className="row glass-hover"
                style={{
                  cursor: 'pointer', padding: '9px 14px', borderRadius: 12, border: '1px solid var(--stroke)',
                  background: active ? 'linear-gradient(120deg, var(--accent-1), var(--accent-2))' : 'var(--surface-2)',
                  color: active ? '#071021' : 'var(--text-2)',
                  boxShadow: active ? '0 6px 20px var(--accent-glow)' : 'none',
                  gap: 8,
                }}
                onClick={() => {
                  setAccent(key)
                  toast(`Theme set: ${key}`, 'success')
                }}
              >
                <span
                  style={{
                    width: 16, height: 16, borderRadius: 99,
                    background: `linear-gradient(120deg, ${vars['--accent-1']}, ${vars['--accent-2']})`,
                    boxShadow: '0 0 8px rgba(255,255,255,0.25)',
                  }}
                />
                <span style={{ fontSize: 12.5, fontWeight: 700, textTransform: 'capitalize' }}>
                  {key}
                </span>
                {active && <Check size={13} />}
              </button>
            )
          })}
        </div>
      </GlassCard>

      <div className="tiny" style={{ textAlign: 'center', lineHeight: 1.7, padding: '0 10px' }}>
        Naam/bhasha update karni hai? → <b style={{ color: 'var(--accent-1)' }}>Memory</b> section mein Handshake Profile edit karo.
      </div>
      </motion.div>
    </motion.div>
  )
}
