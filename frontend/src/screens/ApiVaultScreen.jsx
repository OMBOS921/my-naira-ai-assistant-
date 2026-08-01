import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Lock, ShieldCheck, Loader2 } from 'lucide-react'
import { useApp } from '../state/AppContext.jsx'
import { saveVaultConfiguration, getVaultStatus } from '../api/client.js'
import AvatarStage from '../components/AvatarStage.jsx'
import KeyField from '../components/KeyField.jsx'
import Background3D from '../components/Background3D.jsx'

export default function ApiVaultScreen() {
  const { setScreen, toast, setAvatarState } = useApp()
  const [geminiKey, setGeminiKey] = useState('')
  const [zenKey, setZenKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [skipped, setSkipped] = useState(false)

  useEffect(() => {
    getVaultStatus().then((s) => {
      if (s.configured) {
        setSkipped(true)
        toast('Vault already configured — proceeding automatically', 'info')
        setTimeout(() => setScreen('handshake'), 900)
      }
    })
  }, [setScreen, toast])

  const handleVerify = async () => {
    const gem = geminiKey.trim()
    const zen = zenKey.trim()
    if (!gem && !zen) {
      toast('At least one API key is required', 'error')
      return
    }
    setBusy(true)
    setAvatarState('thinking')
    try {
      const provider = gem ? 'gemini' : 'deepseek'
      await saveVaultConfiguration({
        provider,
        apiKey: gem || zen,
        model: undefined,
      })
      setAvatarState('laughing')
      toast('Key verified & sealed in vault — no restart needed', 'success')
      setTimeout(() => setScreen('handshake'), 800)
    } catch (err) {
      setAvatarState('idle')
      toast(err.message || 'Key verification failed', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 2, display: 'grid', placeItems: 'center', padding: 24 }}>
      <Background3D />
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.15fr)', gap: 56, maxWidth: 980, width: '100%', alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
          <AvatarStage size="md" state="custom" />
          <span className="badge badge-violet" style={{ textTransform: 'none', letterSpacing: '0.06em' }}>
            <Lock size={11} />
            Vault Status: Unlocked
          </span>
          <div style={{ textAlign: 'center' }}>
            <div className="font-display" style={{ fontSize: 22, fontWeight: 700 }}>
              API <span className="grad-text">Vault</span>
            </div>
            <div className="muted" style={{ fontSize: 13.5, marginTop: 8, lineHeight: 1.6, maxWidth: 300 }}>
              Naira ko chalaane ke liye ek API key chahiye. Key verify hote hi <b style={{ color: 'var(--text-1)' }}>backend vault mein auto-save</b> ho jaati hai — dobara kabhi nahi deni padegi.
            </div>
          </div>
        </div>

        <motion.div
          className="glass"
          style={{ padding: 34 }}
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="row" style={{ marginBottom: 24, gap: 12 }}>
            <div style={{ width: 40, height: 40, borderRadius: 13, display: 'grid', placeItems: 'center', background: 'linear-gradient(120deg, var(--accent-1), var(--accent-2))', color: '#071021', boxShadow: '0 6px 24px var(--accent-glow)' }}>
              <ShieldCheck size={19} />
            </div>
            <div>
              <div className="font-display" style={{ fontSize: 17, fontWeight: 700 }}>Secure Key Sealing</div>
              <div className="tiny" style={{ marginTop: 2 }}>Verified by live LLM handshake</div>
            </div>
          </div>

          <KeyField
            label="Gemini API Key"
            dot
            placeholder="AIzaSy..."
            value={geminiKey}
            onChange={setGeminiKey}
            status={zenKey ? 'optional' : 'required'}
            helper="Powers Gemini models — ek hi key kaafi hai"
            getKeyLink="https://aistudio.google.com/apikey"
          />
          <KeyField
            label="OpenCode Zen API Key"
            placeholder="zen-..."
            value={zenKey}
            onChange={setZenKey}
            status={geminiKey ? 'optional' : 'required'}
            helper="Free deepseek-v4-flash endpoint via OpenCode Zen"
            getKeyLink="https://opencode.ai/zen"
          />

          <button className="btn btn-primary" style={{ width: '100%', marginTop: 8 }} disabled={busy} onClick={handleVerify}>
            {busy ? <Loader2 size={17} className="spin" /> : <ShieldCheck size={17} />}
            {busy ? 'Verifying & Sealing...' : 'Verify & Proceed'}
          </button>

          <div className="tiny" style={{ marginTop: 16, textAlign: 'center', textTransform: 'none', letterSpacing: 0, lineHeight: 1.7 }}>
            Backend key ko <b style={{ color: 'var(--text-2)' }}>real LLM call</b> se verify karta hai, phir <b style={{ color: 'var(--text-2)' }}>memory/user_vault.json</b> mein atomic-save — hot reload, server restart nahi.
          </div>
        </motion.div>
      </div>
      {skipped && (
        <motion.div className="glass-soft" style={{ position: 'absolute', bottom: 30, padding: '12px 20px' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <span className="badge badge-mint"><span className="dot" />Vault active — redirecting</span>
        </motion.div>
      )}
    </div>
  )
}
