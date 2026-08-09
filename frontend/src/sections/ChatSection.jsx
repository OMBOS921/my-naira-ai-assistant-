import { useEffect, useRef, useState } from 'react'
import { MessageSquare, Volume2, VolumeX, Send, MicOff } from 'lucide-react'
import { SectionShell, Toggle } from '../components/ui.jsx'
import { useApp } from '../state/AppContext.jsx'
import { formatTime } from '../state/store.js'

export default function ChatSection({ onClose, chatMessages, setChatMessages, speakRef, send, onNavigate }) {
  const { setAvatarState, toast } = useApp()
  const [text, setText] = useState('')
  const [speak, setSpeak] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    speakRef.current = speak
  }, [speak, speakRef])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  const handleSend = () => {
    const msg = text.trim()
    if (!msg) return
    setChatMessages((m) => [...m.slice(-199), { id: `c_${Date.now()}`, ts: Date.now(), sender: 'user', text: msg }])
    setText('')
    setAvatarState('thinking')
    const ok = send(msg)
    if (!ok) {
      toast('Connection offline — backend chal raha hai?', 'error')
      setAvatarState('idle')
    }
  }

  return (
    <SectionShell
      icon={<MessageSquare size={18} />}
      title="Chat"
      subtitle="Typed conversations with Naira"
      onClose={onClose}
    >
      <div
        className="glass-soft"
        style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 16, gap: 10, overflow: 'hidden' }}
      >
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, paddingRight: 4 }}>
          {chatMessages.length === 0 && (
            <div style={{ textAlign: 'center', color: 'var(--text-3)', fontSize: 13, margin: 'auto 0', lineHeight: 1.8 }}>
              <MicOff size={26} style={{ opacity: 0.5, marginBottom: 8 }} />
              <div>Abhi koi conversation nahi.</div>
              <div className="tiny">Voice commands yahan nahi dikhte — woh History mein jate hain.</div>
            </div>
          )}
          {chatMessages.map((m) => (
            <div key={m.id} className={`chat-msg ${m.sender === 'user' ? 'user' : 'naira'}${m.proactive ? ' proactive' : ''}`}>
              <div className={`chat-bubble${m.streaming ? ' streaming' : ''}`}>
                {m.text}
                {m.streaming && <span className="stream-cursor">▌</span>}
              </div>
              <div className="chat-meta">
                {m.sender === 'user' ? 'You' : 'Naira'}
                {m.proactive && ' · 🔔 Proactive'}
                {' · '}{formatTime(m.ts)}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="row" style={{ borderTop: '1px solid var(--stroke)', paddingTop: 12 }}>
          <input
            className="field"
            placeholder="Naira ko kuch bolo..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          />
          <button className="btn btn-primary btn-icon" onClick={handleSend} title="Send">
            <Send size={16} />
          </button>
        </div>
      </div>

      <div className="card between">
        <div className="row" style={{ gap: 12 }}>
          {speak ? <Volume2 size={18} style={{ color: 'var(--accent-1)' }} /> : <VolumeX size={18} style={{ color: 'var(--text-3)' }} />}
          <div>
            <div style={{ fontWeight: 700, fontSize: 13.5 }}>Voice Replies</div>
            <div className="tiny" style={{ textTransform: 'none', letterSpacing: 0 }}>
              {speak ? 'Naira likhegi aur bolegi bhi' : 'Sirf text reply — bol kar nahi batayegi'}
            </div>
          </div>
        </div>
        <Toggle checked={speak} onChange={setSpeak} />
      </div>

      <button className="btn btn-ghost btn-sm" style={{ alignSelf: 'center' }} onClick={() => onNavigate('history')}>
        Voice conversations → History section mein
      </button>
    </SectionShell>
  )
}
