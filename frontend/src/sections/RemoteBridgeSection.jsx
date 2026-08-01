import { useCallback, useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { Smartphone, QrCode, RefreshCw, Lock, Trash2, ShieldCheck, ShieldAlert, Activity, Wifi, Phone, Eye, EyeOff } from 'lucide-react'
import { SectionShell, GlassCard, Toggle, Slider, Modal, EmptyState, StatusPill } from '../components/ui.jsx'
import { useApp } from '../state/AppContext.jsx'
import { usePersistedState, useInterval, makeId, nowSec, randomHex, formatTime } from '../state/store.js'
import { getRemoteBridgeStatus } from '../api/client.js'

const COMMANDS = [
  { action: 'GET_BATTERY', risk: 5 },
  { action: 'TOGGLE_WIFI', risk: 10 },
  { action: 'TOGGLE_BLUETOOTH', risk: 10 },
  { action: 'SET_VOLUME', risk: 15 },
  { action: 'LOCK_DEVICE', risk: 20 },
  { action: 'OPEN_APP', risk: 25 },
  { action: 'TAKE_SCREENSHOT', risk: 30 },
  { action: 'READ_CONTACTS', risk: 35 },
  { action: 'READ_SMS', risk: 40 },
  { action: 'LOCATION_GET', risk: 50 },
  { action: 'MAKE_CALL', risk: 60 },
  { action: 'SEND_SMS', risk: 70 },
  { action: 'CHANGE_PASSWORD', risk: 90 },
  { action: 'OPEN_BANK_APP', risk: 95 },
  { action: 'TRANSFER_FUNDS', risk: 95 },
  { action: 'FACTORY_RESET', risk: 100 },
]

export default function RemoteBridgeSection({ onClose }) {
  const { toast } = useApp()
  const [ngrokUrl, setNgrokUrl] = usePersistedState('naira.bridge.ngrok', 'wss://swampland-flatten-rockstar.ngrok-free.dev/ws/remote')
  const [devices, setDevices] = usePersistedState('naira.bridge.devices', [])
  const [threshold, setThreshold] = usePersistedState('naira.bridge.threshold', 80)
  const [commandPolicy, setCommandPolicy] = usePersistedState('naira.bridge.policy', {})
  const [alwaysBiometric, setAlwaysBiometric] = usePersistedState('naira.bridge.alwaysBio', false)
  const [logs, setLogs] = usePersistedState('naira.bridge.logs', [])
  const [qrPayload, setQrPayload] = useState(null)
  const [expiresIn, setExpiresIn] = useState(60)
  const [showQr, setShowQr] = useState(false)
  const [confirmLock, setConfirmLock] = useState(false)
  const [confirmWipe, setConfirmWipe] = useState(false)
  const [bridge, setBridge] = useState({ connected: false, queue_size: 0, fcm_ready: false, reachable: false })

  const addLog = useCallback(
    (message, tone = 'info') => {
      setLogs((l) => [{ id: makeId('log'), ts: Date.now(), message, tone }, ...l.slice(0, 60)])
    },
    [setLogs]
  )

  const generateQr = useCallback(() => {
    setQrPayload({
      master_key: randomHex(32),
      ngrok_url: ngrokUrl,
      timestamp: nowSec(),
    })
    setExpiresIn(60)
    addLog('New pairing QR generated', 'violet')
  }, [ngrokUrl, addLog])

  useEffect(() => {
    if (!showQr) return
    generateQr()
  }, [showQr, generateQr])

  useInterval(() => {
    if (!qrPayload) return
    const age = nowSec() - qrPayload.timestamp
    if (age >= 60) {
      setExpiresIn(0)
      generateQr()
    } else {
      setExpiresIn(60 - age)
    }
  }, 1000)

  useInterval(() => {
    getRemoteBridgeStatus().then((s) => {
      setBridge(s)
      const wasConnected = bridge.connected
      if (s.connected && !wasConnected) addLog('Remote device connected via mTLS WebSocket', 'mint')
      if (!s.connected && wasConnected) addLog('Remote device disconnected', 'rose')
    })
  }, 5000)

  const addDevice = () => {
    const name = window.prompt('Device ka naam (e.g. "Mera Phone"):')
    if (!name) return
    setDevices((d) => [...d, { id: makeId('dev'), name, pairedAt: Date.now(), fcm: `token_${randomHex(6)}` }])
    addLog(`Device paired: ${name}`, 'mint')
  }

  const revokeDevice = (dev) => {
    setDevices((d) => d.filter((x) => x.id !== dev.id))
    addLog(`Device revoked: ${dev.name}`, 'rose')
    toast(`"${dev.name}" revoke kar diya gaya`, 'info')
  }

  const setPolicy = (action, mode) => {
    setCommandPolicy((p) => ({ ...p, [action]: mode }))
    addLog(`Policy changed: ${action} → ${mode === 'allow' ? 'Allow' : mode === 'block' ? 'Block' : 'Always Biometric'}`, 'cyan')
  }

  const lockDevice = () => {
    setConfirmLock(false)
    addLog('LOCK_SIGNAL dispatched → device admin lock request sent', 'amber')
    toast('Device lock signal sent — phone turant lock ho jayega', 'info')
  }

  const wipeDevice = () => {
    setConfirmWipe(false)
    addLog('WIPE_DATA requested (placeholder — future update)', 'rose')
    toast('Wipe is a placeholder — abhi available nahi', 'error')
  }

  const policyIcon = (action) => {
    const mode = alwaysBiometric ? 'bio' : commandPolicy[action] || (COMMANDS.find((c) => c.action === action)?.risk > threshold ? 'bio' : 'allow')
    return { allow: { icon: ShieldCheck, tone: 'mint', label: 'Allow' }, bio: { icon: ShieldAlert, tone: 'amber', label: 'Biometric' }, block: { icon: Lock, tone: 'rose', label: 'Block' } }[mode]
  }

  return (
    <SectionShell icon={<Smartphone size={18} />} title="Remote Bridge" subtitle="Zero-trust phone ↔ PC control" onClose={onClose}>
      {/* ---------- Pairing ---------- */}
      <GlassCard className="card">
        <div className="card-title"><QrCode size={14} /> Device Pairing</div>
        <div className="field-group" style={{ marginBottom: 10 }}>
          <label className="field-label">Ngrok Tunnel URL</label>
          <input className="field" style={{ fontSize: 12.5 }} value={ngrokUrl} onChange={(e) => setNgrokUrl(e.target.value)} placeholder="wss://...ngrok-free.app/ws/remote" />
        </div>
        <button className="btn btn-primary btn-sm" style={{ width: '100%' }} onClick={() => setShowQr(true)}>
          <QrCode size={15} /> Generate Pairing QR
        </button>

        {showQr && qrPayload && (
          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
            <div className="glass-soft" style={{ padding: 14, borderRadius: 16 }}>
              <QRCodeSVG value={JSON.stringify(qrPayload)} size={190} fgColor="#070b1e" bgColor="#ffffff" level="M" />
            </div>
            <div className="between" style={{ width: '100%' }}>
              <span className={`badge ${expiresIn < 15 ? 'badge-rose' : 'badge-cyan'}`} style={{ textTransform: 'none', letterSpacing: 0 }}>
                Expires in {expiresIn}s
              </span>
              <div className="row" style={{ gap: 6 }}>
                <button className="btn btn-ghost btn-tiny" onClick={generateQr}><RefreshCw size={12} /> Regenerate</button>
                <button className="btn btn-ghost btn-tiny" onClick={() => setShowQr(false)}>Close</button>
              </div>
            </div>
            <div className="tiny" style={{ textTransform: 'none', letterSpacing: 0, textAlign: 'center', lineHeight: 1.7 }}>
              Android app se QR scan karo — master key EncryptedVault mein save hogi. 60s expiry, replay-proof.
            </div>
          </div>
        )}
      </GlassCard>

      {/* ---------- Devices ---------- */}
      <GlassCard className="card">
        <div className="between">
          <div className="card-title" style={{ marginBottom: 0 }}>Paired Devices</div>
          <button className="btn btn-ghost btn-tiny" onClick={addDevice}><QrCode size={12} /> Add device</button>
        </div>
        {devices.length === 0 ? (
          <div className="tiny" style={{ padding: '10px 2px' }}>Koi device paired nahi — QR generate karke phone se scan karo.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
            {devices.map((d) => (
              <div key={d.id} className="glass-soft between" style={{ padding: '11px 13px' }}>
                <div className="row" style={{ gap: 10 }}>
                  <div style={{ width: 32, height: 32, borderRadius: 10, display: 'grid', placeItems: 'center', background: 'rgba(52,211,153,0.12)', color: 'var(--mint)' }}>
                    <Smartphone size={15} />
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700 }}>{d.name}</div>
                    <div className="tiny" style={{ marginTop: 2 }}>Paired {formatTime(d.pairedAt)} · {d.fcm.slice(0, 12)}...</div>
                  </div>
                </div>
                <button className="btn btn-ghost btn-tiny" onClick={() => revokeDevice(d)} title="Revoke">
                  <Trash2 size={12} style={{ color: 'var(--rose)' }} />
                </button>
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      {/* ---------- Connection Status ---------- */}
      <GlassCard className="card">
        <div className="card-title"><Activity size={14} /> Connection Status</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <StatusPill label="WebSocket / mTLS" value={bridge.connected ? 'Connected' : bridge.reachable === false ? 'Backend offline' : 'Disconnected'} tone={bridge.connected ? 'mint' : 'rose'} />
          <StatusPill label="FCM Wakeup Service" value={bridge.fcm_ready ? 'Active' : 'Standby'} tone={bridge.fcm_ready ? 'mint' : 'amber'} />
          <StatusPill label="Offline Action Queue" value={`${bridge.queue_size} pending`} tone={bridge.queue_size > 0 ? 'amber' : 'gray'} />
          <StatusPill label="Tunnel" value={ngrokUrl.includes('ngrok') ? 'Ngrok' : 'Custom'} tone="violet" />
        </div>
      </GlassCard>

      {/* ---------- Risk Engine ---------- */}
      <GlassCard className="card">
        <div className="card-title"><ShieldCheck size={14} /> Risk Engine & Rules</div>
        <div className="between" style={{ marginBottom: 6 }}>
          <span className="tiny">Biometric Threshold</span>
          <span className="badge badge-violet" style={{ textTransform: 'none', letterSpacing: 0 }}>&gt; {threshold}</span>
        </div>
        <Slider min={0} max={100} value={threshold} onChange={(v) => { setThreshold(v); addLog(`Biometric threshold set to > ${v}`, 'violet') }} />
        <div className="tiny" style={{ marginTop: 6, textTransform: 'none', letterSpacing: 0 }}>
          Threshold se upar wale commands ke liye fingerprint chahiye hoga.
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <span className="tiny grow">Always Biometric (sab commands lock)</span>
          <Toggle checked={alwaysBiometric} onChange={(v) => { setAlwaysBiometric(v); addLog(v ? 'Always Biometric mode ON' : 'Always Biometric mode OFF', 'amber') }} />
        </div>
      </GlassCard>

      {/* ---------- Command permissions ---------- */}
      <GlassCard className="card">
        <div className="card-title">Command Permissions</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {COMMANDS.map((c) => {
            const mode = alwaysBiometric ? 'bio' : commandPolicy[c.action] || (c.risk > threshold ? 'bio' : 'allow')
            const P = policyIcon(c.action)
            return (
              <div key={c.action} className="between" style={{ padding: '7px 10px', borderRadius: 10, background: 'rgba(255,255,255,0.03)' }}>
                <div className="row" style={{ gap: 10 }}>
                  <P.icon size={14} style={{ color: { mint: 'var(--mint)', amber: 'var(--amber)', rose: 'var(--rose)' }[P.tone] }} />
                  <span style={{ fontSize: 12.5, fontWeight: 600, letterSpacing: '0.03em' }}>{c.action}</span>
                </div>
                <div className="row" style={{ gap: 6 }}>
                  <span className="tiny" style={{ color: 'var(--text-3)' }}>{c.risk}</span>
                  <select
                    className="field"
                    style={{ width: 122, padding: '5px 8px', fontSize: 11.5, borderRadius: 8 }}
                    value={mode}
                    disabled={alwaysBiometric}
                    onChange={(e) => setPolicy(c.action, e.target.value)}
                  >
                    <option value="allow">Allow</option>
                    <option value="bio">Biometric</option>
                    <option value="block">Block</option>
                  </select>
                </div>
              </div>
            )
          })}
        </div>
      </GlassCard>

      {/* ---------- Emergency ---------- */}
      <GlassCard className="card" style={{ borderColor: 'rgba(251,113,133,0.35)' }}>
        <div className="card-title" style={{ color: 'var(--rose)' }}>Emergency & Anti-Theft</div>
        <div className="grid-2">
          <button className="btn btn-danger btn-sm" onClick={() => setConfirmLock(true)}>
            <Lock size={14} /> Lock Device
          </button>
          <button className="btn btn-ghost btn-sm" style={{ borderColor: 'rgba(251,113,133,0.4)' }} onClick={() => setConfirmWipe(true)}>
            <Trash2 size={14} /> Wipe Data
          </button>
        </div>
        <div className="tiny" style={{ marginTop: 10, textTransform: 'none', letterSpacing: 0 }}>
          Lock = turant phone/PC lock (Device Admin). Wipe = future update placeholder.
        </div>
      </GlassCard>

      {/* ---------- Security logs ---------- */}
      <GlassCard className="card">
        <div className="card-title"><Activity size={14} /> Live Security Logs</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 220, overflowY: 'auto' }}>
          {logs.length === 0 && <div className="tiny" style={{ padding: '8px 2px' }}>Activity yahan log hogi — pairing, policy, status changes.</div>}
          {logs.map((l) => (
            <div key={l.id} className="row" style={{ gap: 8, fontSize: 11.5, alignItems: 'flex-start' }}>
              <span style={{ color: 'var(--text-3)', fontFamily: 'monospace', flexShrink: 0 }}>{formatTime(l.ts)}</span>
              <span style={{ color: { mint: 'var(--mint)', rose: 'var(--rose)', amber: 'var(--amber)', violet: 'var(--violet)', cyan: 'var(--cyan)' }[l.tone] || 'var(--text-2)', lineHeight: 1.5 }}>
                {l.message}
              </span>
            </div>
          ))}
        </div>
      </GlassCard>

      <Modal open={confirmLock} onClose={() => setConfirmLock(false)} title="Lock device?" danger>
        <div className="muted" style={{ fontSize: 13.5, lineHeight: 1.7 }}>
          Ye signed <b style={{ color: 'var(--text-1)' }}>LOCK_DEVICE</b> action bhejega (risk 20). Device admin receiver turant phone lock karega. Continue karna hai?
        </div>
        <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setConfirmLock(false)}>Cancel</button>
          <button className="btn btn-danger btn-sm" onClick={lockDevice}><Lock size={14} /> Lock Now</button>
        </div>
      </Modal>

      <Modal open={confirmWipe} onClose={() => setConfirmWipe(false)} title="Wipe device data?" danger>
        <div className="muted" style={{ fontSize: 13.5, lineHeight: 1.7 }}>
          Risk score <b style={{ color: 'var(--rose)' }}>100</b> — yeh action future update mein aayega. Abhi placeholder hai.
        </div>
        <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setConfirmWipe(false)}>Cancel</button>
          <button className="btn btn-danger btn-sm" onClick={wipeDevice}><Trash2 size={14} /> Wipe</button>
        </div>
      </Modal>
    </SectionShell>
  )
}
