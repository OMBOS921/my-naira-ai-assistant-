import { useEffect, useState } from 'react'
import { Home as HomeIcon, Cpu, Wifi, Database, MessageSquare, Smartphone, Sparkles } from 'lucide-react'
import { SectionShell, GlassCard, StatusPill } from '../components/ui.jsx'
import { getVaultStatus } from '../api/client.js'

export default function HomeSection({ onClose, onNavigate, profile, chatMessages, historyItems, wsStatus }) {
  const [vault, setVault] = useState(null)

  useEffect(() => {
    getVaultStatus().then(setVault)
  }, [])

  const stats = [
    { icon: MessageSquare, label: 'Chat messages', value: chatMessages.length },
    { icon: Sparkles, label: 'Voice conversations', value: historyItems.length },
    { icon: Database, label: 'Vault provider', value: vault?.provider === 'gemini' ? 'Gemini' : vault?.provider ? 'DeepSeek (Zen)' : '—' },
    { icon: Smartphone, label: 'Memory slots', value: 6 },
  ]

  return (
    <SectionShell icon={<HomeIcon size={18} />} title="Home" subtitle="System overview" onClose={onClose}>
      <div className="card fade-up" style={{ background: 'linear-gradient(140deg, rgba(34,211,238,0.12), rgba(167,139,250,0.1))' }}>
        <div className="row" style={{ gap: 14 }}>
          <div style={{ width: 44, height: 44, borderRadius: 14, display: 'grid', placeItems: 'center', background: 'linear-gradient(120deg, var(--accent-1), var(--accent-2))', color: '#071021', boxShadow: '0 8px 26px var(--accent-glow)' }}>
            <Sparkles size={20} />
          </div>
          <div>
            <div className="font-display" style={{ fontSize: 16, fontWeight: 700 }}>
              Namaste, {profile?.name || 'Operator'} {profile?.tone === 'playful' ? '✨' : '🌸'}
            </div>
            <div className="muted" style={{ fontSize: 12.5, marginTop: 3 }}>
              Naira aapke saath hai — kuch bhi bolo, main sun loongi.
            </div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        {stats.map((s) => (
          <GlassCard key={s.label} className="card" hover style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 14 }}>
            <s.icon size={16} style={{ color: 'var(--accent-1)' }} />
            <div className="font-display" style={{ fontSize: 22, fontWeight: 800 }}>{s.value}</div>
            <div className="tiny">{s.label}</div>
          </GlassCard>
        ))}
      </div>

      <GlassCard className="card">
        <div className="card-title"><Cpu size={14} /> System Status</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <StatusPill label="Neural Link (WS)" value={wsStatus === 'online' ? 'Connected' : wsStatus === 'connecting' ? 'Connecting' : 'Offline'} tone={wsStatus === 'online' ? 'mint' : wsStatus === 'connecting' ? 'amber' : 'rose'} />
          <StatusPill label="API Vault" value={vault?.configured ? 'Sealed' : 'Empty'} tone={vault?.configured ? 'mint' : 'amber'} />
          <StatusPill label="Remote Bridge" value="Standby" tone="gray" />
          <StatusPill label="Voice Engine" value="RVC Ready" tone="violet" />
        </div>
      </GlassCard>

      <div className="grid-2">
        {[
          { id: 'chat', label: 'Open Chat', desc: 'Typed conversations' },
          { id: 'bridge', label: 'Remote Bridge', desc: 'Phone control' },
          { id: 'voice', label: 'Voice Studio', desc: 'RVC voices' },
        ].map((b) => (
          <button key={b.id} className="card glass-hover" style={{ textAlign: 'left', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 4 }} onClick={() => onNavigate(b.id)}>
            <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-1)' }}>{b.label}</div>
            <div className="tiny" style={{ textTransform: 'none', letterSpacing: 0 }}>{b.desc}</div>
          </button>
        ))}
      </div>

      <div className="row" style={{ justifyContent: 'center', gap: 8 }}>
        <Wifi size={13} style={{ color: 'var(--mint)' }} />
        <span className="tiny">All systems operational</span>
      </div>
    </SectionShell>
  )
}
