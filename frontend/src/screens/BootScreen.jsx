import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useApp } from '../state/AppContext.jsx'
import { getVaultStatus } from '../api/client.js'
import AvatarStage from '../components/AvatarStage.jsx'
import Background3D from '../components/Background3D.jsx'

const BOOT_STEPS = [
  'Booting neural kernel',
  'Mounting memory core',
  'Syncing vault bridge',
  'Calibrating voice matrix',
  'Naira online',
]

export default function BootScreen() {
  const { setScreen, profile } = useApp()
  const [progress, setProgress] = useState(0)
  const [stepIdx, setStepIdx] = useState(0)
  const started = useRef(false)

  useEffect(() => {
    const total = 3000
    const interval = setInterval(() => {
      setProgress((p) => Math.min(100, p + (100 / (total / 40))))
      setStepIdx(Math.min(BOOT_STEPS.length - 1, Math.floor((progress / 100) * BOOT_STEPS.length)))
    }, 40)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (progress < 100 || started.current) return
    started.current = true
    const go = async () => {
      const status = await getVaultStatus()
      if (status.configured && profile) setScreen('dashboard')
      else if (status.configured) setScreen('handshake')
      else setScreen('vault')
    }
    const t = setTimeout(go, 600)
    return () => clearTimeout(t)
  }, [progress, setScreen, profile])

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', zIndex: 2 }}>
      <Background3D />
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26, maxWidth: 420, width: '92%' }}>
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          style={{ textAlign: 'center' }}
        >
          <div className="font-display" style={{ fontSize: 34, fontWeight: 800, letterSpacing: '0.28em' }}>
            <span className="grad-text">NAIRA</span> <span style={{ color: 'var(--text-1)' }}>OS</span>
          </div>
          <div className="tiny" style={{ marginTop: 6 }}>Personal AI Operating System</div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.7 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1], delay: 0.15 }}
        >
          <AvatarStage size="md" state="idle" />
        </motion.div>

        <div style={{ width: '100%' }}>
          <div className="progress-track">
            <div className="progress-bar" style={{ width: `${progress}%` }} />
          </div>
          <div className="row" style={{ marginTop: 10, justifyContent: 'space-between' }}>
            <span className="tiny">{BOOT_STEPS[Math.min(stepIdx, BOOT_STEPS.length - 1)]}...</span>
            <span className="tiny" style={{ color: 'var(--cyan)' }}>{Math.round(progress)}%</span>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 7, width: '100%' }}>
          {BOOT_STEPS.map((s, i) => (
            <div key={s} className={`boot-line ${i < stepIdx || progress >= 100 ? 'done' : ''}`}>
              {i < stepIdx || progress >= 100 ? (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6 9 17l-5-5" />
                </svg>
              ) : (
                <span style={{ width: 13, height: 13, borderRadius: 99, border: '1px solid var(--text-3)', opacity: 0.4 }} />
              )}
              <span>{s}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
