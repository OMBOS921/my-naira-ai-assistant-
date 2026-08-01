import { History, Trash2, Volume2, User, Sparkles } from 'lucide-react'
import { SectionShell, GlassCard, EmptyState } from '../components/ui.jsx'
import { groupByDate, formatTime } from '../state/store.js'

export default function HistorySection({ onClose, historyItems, setHistoryItems, speakRef }) {
  const groups = groupByDate(historyItems, 'ts')

  const clearAll = () => {
    if (window.confirm('Saari voice conversations delete karni hain?')) setHistoryItems([])
  }

  return (
    <SectionShell icon={<History size={18} />} title="History" subtitle="Voice conversations with Naira" onClose={onClose}>
      {historyItems.length > 0 && (
        <div className="between">
          <span className="tiny">{historyItems.length} conversations</span>
          <button className="btn btn-ghost btn-tiny" onClick={clearAll}>
            <Trash2 size={12} /> Clear all
          </button>
        </div>
      )}

      {historyItems.length === 0 ? (
        <EmptyState
          icon={<History size={30} />}
          title="No voice conversations yet"
          note="Mic dabake Naira se baat karo — har conversation yahan save hoga, chat mein nahi."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {groups.map((g) => (
            <div key={g.label}>
              <div className="tiny" style={{ marginBottom: 10, color: 'var(--accent-2)' }}>{g.label}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {g.items.map((item) => (
                  <GlassCard key={item.id} className="card" style={{ padding: 14 }}>
                    <div className="row" style={{ gap: 10, marginBottom: 8 }}>
                      <div style={{ width: 30, height: 30, borderRadius: 10, display: 'grid', placeItems: 'center', background: 'rgba(34,211,238,0.12)', color: 'var(--cyan)', flexShrink: 0 }}>
                        <User size={14} />
                      </div>
                      <div className="grow">
                        <div style={{ fontSize: 13.5, lineHeight: 1.5, color: 'var(--text-1)' }}>{item.user}</div>
                        <div className="tiny" style={{ marginTop: 3 }}>{formatTime(item.ts)}</div>
                      </div>
                      <button
                        className="btn btn-ghost btn-tiny"
                        title="Speak reply"
                        onClick={() => {
                          if ('speechSynthesis' in window) {
                            const u = new SpeechSynthesisUtterance(item.naira)
                            u.lang = 'hi-IN'
                            u.rate = 1
                            window.speechSynthesis.speak(u)
                          }
                        }}
                      >
                        <Volume2 size={12} />
                      </button>
                    </div>
                    <div className="row" style={{ gap: 10, alignItems: 'flex-start' }}>
                      <div style={{ width: 30, height: 30, borderRadius: 10, display: 'grid', placeItems: 'center', background: 'rgba(167,139,250,0.12)', color: 'var(--violet)', flexShrink: 0 }}>
                        <Sparkles size={14} />
                      </div>
                      <div style={{ fontSize: 13, lineHeight: 1.55, color: 'var(--text-2)' }}>{item.naira}</div>
                    </div>
                  </GlassCard>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionShell>
  )
}
