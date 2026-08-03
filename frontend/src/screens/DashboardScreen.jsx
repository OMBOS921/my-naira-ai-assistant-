import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Home, Brain, History, MessageSquare, Smartphone, Puzzle, AudioLines, Settings, Mic, Square } from 'lucide-react'
import { useApp } from '../state/AppContext.jsx'
import AvatarStage from '../components/AvatarStage.jsx'
import Background3D from '../components/Background3D.jsx'
import HomeSection from '../sections/HomeSection.jsx'
import MemorySection from '../sections/MemorySection.jsx'
import HistorySection from '../sections/HistorySection.jsx'
import ChatSection from '../sections/ChatSection.jsx'
import RemoteBridgeSection from '../sections/RemoteBridgeSection.jsx'
import PluginsSection from '../sections/PluginsSection.jsx'
import VoiceSection from '../sections/VoiceSection.jsx'
import SettingsSection from '../sections/SettingsSection.jsx'

const NAV = [
  { id: 'home', icon: Home, label: 'Home', Comp: HomeSection },
  { id: 'memory', icon: Brain, label: 'Memory', Comp: MemorySection },
  { id: 'history', icon: History, label: 'History', Comp: HistorySection },
  { id: 'chat', icon: MessageSquare, label: 'Chat', Comp: ChatSection },
  { id: 'bridge', icon: Smartphone, label: 'Remote Bridge', Comp: RemoteBridgeSection },
  { id: 'plugins', icon: Puzzle, label: 'Plugins', Comp: PluginsSection },
  { id: 'voice', icon: AudioLines, label: 'Voice', Comp: VoiceSection },
]

const EMPTY_CHAT = []
const EMPTY_HISTORY = []
const EMPTY_TOOLS = []

export default function DashboardScreen() {
  const { profile, avatarState, setAvatarState, connect, send, setOnMessage, toast, wsStatus, accent } = useApp()

  const [activeSection, setActiveSection] = useState(null)
  const [showSettings, setShowSettings] = useState(false)

  const [chatMessages, setChatMessages] = useState(() => {
    try { return JSON.parse(localStorage.getItem('naira.chat')) || EMPTY_CHAT } catch { return EMPTY_CHAT }
  })
  const [historyItems, setHistoryItems] = useState(() => {
    try { return JSON.parse(localStorage.getItem('naira.history')) || EMPTY_HISTORY } catch { return EMPTY_HISTORY }
  })
  const [toolLogs, setToolLogs] = useState(() => {
    try { return JSON.parse(localStorage.getItem('naira.tools')) || EMPTY_TOOLS } catch { return EMPTY_TOOLS }
  })

  const speakRef = useRef(false)
  const sourceRef = useRef('chat')
  const pendingHistoryRef = useRef(null)
  const audioRef = useRef(null)
  const [wakeActive, setWakeActive] = useState(false)

  useEffect(() => {
    localStorage.setItem('naira.chat', JSON.stringify(chatMessages.slice(-200)))
  }, [chatMessages])
  useEffect(() => {
    localStorage.setItem('naira.history', JSON.stringify(historyItems.slice(-100)))
  }, [historyItems])
  useEffect(() => {
    localStorage.setItem('naira.tools', JSON.stringify(toolLogs.slice(-200)))
  }, [toolLogs])

  const playAudio = useCallback(
    (b64, format = 'mp3') => {
      try {
        const audio = new Audio(`data:audio/${format};base64,${b64}`)
        audioRef.current?.pause()
        audioRef.current = audio
        audio.onplay = () => setAvatarState('talking')
        audio.onended = () => setAvatarState('idle')
        audio.onerror = () => setAvatarState('idle')
        audio.play().catch(() => setAvatarState('idle'))
      } catch {
        setAvatarState('idle')
      }
    },
    [setAvatarState]
  )

  useEffect(() => {
    connect()
    setOnMessage((data) => {
      if (data.type === 'tool_execution_start' || data.type === 'tool_execution_result') {
        setToolLogs((logs) => [
          ...logs.slice(-199),
          {
            id: Math.random().toString(36).slice(2),
            ts: Date.now(),
            type: data.type,
            tool: data.tool,
            text: data.type.includes('start')
              ? `Executing tool: ${data.tool}`
              : `Result: ${(data.output || data.stdout || data.text || '').slice(0, 300)}`,
          },
        ])
        return
      }
      if (data.type === 'wake_word_activated') {
        setWakeActive(true)
        setAvatarState('listening')
        return
      }
      if (data.type === 'barge_in_acknowledged') {
        setAvatarState('listening')
        return
      }
      if (!data.text) return

      if (sourceRef.current === 'voice') {
        const pending = pendingHistoryRef.current
        setHistoryItems((h) => {
          if (pending && pending.user) {
            return [
              ...h,
              { id: `h_${Date.now()}`, ts: Date.now(), user: pending.user, naira: data.text },
            ]
          }
          return h
        })
        pendingHistoryRef.current = null
        playAudio(data.audio)
      } else if (sourceRef.current === 'coding') {
        sourceRef.current = 'chat'
        setToolLogs((logs) => [
          ...logs.slice(-199),
          {
            id: Math.random().toString(36).slice(2),
            ts: Date.now(),
            type: 'agent_output',
            tool: 'Naira Agent',
            text: data.text,
          },
        ])
        setAvatarState('idle')
      } else {
        setChatMessages((m) => [...m.slice(-199), { id: `c_${Date.now()}`, ts: Date.now(), sender: 'naira', text: data.text }])
        if (speakRef.current && data.audio) playAudio(data.audio)
        else setAvatarState('idle')
      }
    })
    return () => setOnMessage(null)
  }, [connect, setOnMessage, playAudio, setAvatarState])

  // ---------- Voice (mic) ----------
  const recognitionRef = useRef(null)
  const [micOn, setMicOn] = useState(false)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])

  // Read the offline STT setting from localStorage (set by SettingsSection)
  const offlineSttEnabled = () => {
    try {
      return JSON.parse(localStorage.getItem('naira.settings.offlineStt')) === true
    } catch { return false }
  }

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const rec = new SR()
    recognitionRef.current = rec
    rec.continuous = true
    rec.interimResults = true
    rec.lang = 'hi-IN'
    let accumulated = ''
    let silenceTimer = null

    const sendTranscript = () => {
      const text = accumulated.trim()
      accumulated = ''
      if (silenceTimer) clearTimeout(silenceTimer)
      if (!text) return
      sourceRef.current = 'voice'
      pendingHistoryRef.current = { user: text }
      setAvatarState('thinking')
      if (!send(text)) {
        pendingHistoryRef.current = null
        toast('Connection offline — command send nahi hui', 'error')
        setAvatarState('idle')
      }
    }

    rec.onstart = () => {
      setMicOn(true)
      setAvatarState('listening')
    }
    rec.onresult = (e) => {
      let current = ''
      for (let i = e.resultIndex; i < e.results.length; i++) current += e.results[i][0].transcript
      if (current.trim()) accumulated = current.trim()
      if (silenceTimer) clearTimeout(silenceTimer)
      silenceTimer = setTimeout(sendTranscript, 1800)
    }
    rec.onerror = (e) => {
      if (e.error === 'no-speech' || e.error === 'aborted') return
      setMicOn(false)
      setAvatarState('idle')
    }
    rec.onend = () => {
      setMicOn(false)
      if (accumulated.trim()) sendTranscript()
      else if (avatarState === 'listening') setAvatarState('idle')
    }
    return () => {
      try { rec.stop() } catch { /* */ }
      if (silenceTimer) clearTimeout(silenceTimer)
    }
  }, [send, toast, setAvatarState])

  // Offline STT: record audio via MediaRecorder and POST to backend
  const startOfflineRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = mr
      chunksRef.current = []
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        chunksRef.current = []
        setMicOn(false)
        setAvatarState('thinking')
        try {
          const { transcribeAudio } = await import('../api/client.js')
          const res = await transcribeAudio(blob)
          const text = (res?.text || '').trim()
          if (text) {
            sourceRef.current = 'voice'
            pendingHistoryRef.current = { user: text }
            if (!send(text)) {
              pendingHistoryRef.current = null
              toast('Connection offline — command send nahi hui', 'error')
              setAvatarState('idle')
            }
          } else {
            toast('No speech detected in recording', 'info')
            setAvatarState('idle')
          }
        } catch (err) {
          toast(err.message || 'Backend STT failed', 'error')
          setAvatarState('idle')
        }
      }
      mr.start()
      setMicOn(true)
      setAvatarState('listening')
    } catch (err) {
      toast('Microphone access denied', 'error')
    }
  }

  const stopOfflineRecording = () => {
    const mr = mediaRecorderRef.current
    if (mr && mr.state !== 'inactive') {
      mr.stop()
    }
  }

  const toggleMic = () => {
    // Barge-in handling
    if (avatarState === 'talking') {
      send({ type: 'barge_in' })
      setAvatarState('listening')
      return
    }

    // Offline STT path
    if (offlineSttEnabled()) {
      if (micOn) {
        stopOfflineRecording()
      } else {
        startOfflineRecording()
      }
      return
    }

    // Browser STT path (default)
    const rec = recognitionRef.current
    if (!rec) {
      toast('Voice input is not supported in this browser', 'error')
      return
    }
    if (micOn) {
      try { rec.stop() } catch { /* */ }
    } else {
      try { rec.start() } catch { /* */ }
    }
  }

  const ActiveComp = NAV.find((n) => n.id === activeSection)?.Comp

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex' }}>
      <Background3D />

      {/* ---------- Left Sidebar ---------- */}
      <aside className="sidebar">
        <div style={{ marginBottom: 10, display: 'grid', placeItems: 'center' }}>
          <div
            className="font-display"
            style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.18em' }}
          >
            <span className="grad-text">N</span>
          </div>
        </div>
        {NAV.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            className={`sidebar-btn ${activeSection === id ? 'active' : ''}`}
            onClick={() => setActiveSection((cur) => (cur === id ? null : id))}
          >
            <Icon size={20} />
            <span className="sidebar-tooltip">{label}</span>
          </button>
        ))}
        <div className="sidebar-spacer" />
        <button
          className={`sidebar-btn ${showSettings ? 'active' : ''}`}
          onClick={() => setShowSettings((s) => !s)}
          title="Settings"
        >
          <Settings size={20} />
          <span className="sidebar-tooltip">Settings</span>
        </button>
      </aside>

      {/* ---------- Center Stage ---------- */}
      <motion.main
        style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        animate={{ paddingRight: activeSection || showSettings ? 460 : 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 32 }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22 }}>
          <div style={{ textAlign: 'center', marginBottom: 4 }}>
            <div className="font-display" style={{ fontSize: 15, letterSpacing: '0.2em', fontWeight: 600 }}>
              <span className="grad-text">NAIRA</span> <span className="muted">OS</span>
            </div>
            <div className="tiny" style={{ marginTop: 4, textTransform: 'none', letterSpacing: 0 }}>
              {profile?.name ? `Welcome back, ${profile.name}` : 'Welcome back'}
              <span className={`badge badge-${wsStatus === 'online' ? 'mint' : wsStatus === 'connecting' ? 'amber' : 'rose'}`} style={{ marginLeft: 10, textTransform: 'none', letterSpacing: 0 }}>
                <span className="dot" />{wsStatus === 'online' ? 'Neural link active' : wsStatus === 'connecting' ? 'Connecting...' : 'Offline'}
              </span>
            </div>
          </div>

          <AvatarStage size="lg" state="custom" />

          {/* Mic below avatar */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <button className={`mic-btn ${micOn ? 'on' : ''}`} onClick={toggleMic} title={avatarState === 'talking' ? 'Interrupt — Naira ko rok do' : 'Toggle listening'}>
              {avatarState === 'talking' ? <Square size={20} /> : <Mic size={22} />}
              <span className="mic-pulse" />
            </button>
            <span className={`mic-label ${micOn ? 'on' : ''}`}>
              {micOn ? 'Naira Listening' : avatarState === 'talking' ? 'Naira Speaking' : avatarState === 'thinking' ? 'Naira Thinking' : 'Naira Idle'}
            </span>
            {wakeActive && (
              <span className="badge badge-cyan" style={{ marginTop: 8, textTransform: 'none', letterSpacing: 0 }}>
                <span className="dot" /> Wake word heard — {profile?.wakeWord || 'Hey Naira'}
              </span>
            )}
          </div>
        </div>
      </motion.main>

      {/* ---------- Slide-in Section Panel ---------- */}
      <AnimatePresence>
        {ActiveComp && (
          <ActiveComp
            key={activeSection}
            onClose={() => setActiveSection(null)}
            profile={profile}
            wsStatus={wsStatus}
            chatMessages={chatMessages}
            setChatMessages={setChatMessages}
            historyItems={historyItems}
            setHistoryItems={setHistoryItems}
            toolLogs={toolLogs}
            setToolLogs={setToolLogs}
            speakRef={speakRef}
            sourceRef={sourceRef}
            send={send}
            onNavigate={setActiveSection}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showSettings && (
          <SettingsSection
            key="settings"
            onClose={() => setShowSettings(false)}
            accent={accent}
            onNavigate={setActiveSection}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
