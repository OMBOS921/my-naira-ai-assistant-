import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { WS_URL } from '../api/client.js'

export const AppContext = createContext(null)

const ACCENTS = {
  aurora: { '--accent-1': '#22d3ee', '--accent-2': '#a78bfa', '--accent-3': '#f472b6', '--accent-glow': 'rgba(34,211,238,0.45)' },
  cyber: { '--accent-1': '#22d3ee', '--accent-2': '#60a5fa', '--accent-3': '#38bdf8', '--accent-glow': 'rgba(34,211,238,0.45)' },
  sakura: { '--accent-1': '#f472b6', '--accent-2': '#c084fc', '--accent-3': '#fb7185', '--accent-glow': 'rgba(244,114,182,0.4)' },
  mint: { '--accent-1': '#34d399', '--accent-2': '#22d3ee', '--accent-3': '#a3e635', '--accent-glow': 'rgba(52,211,153,0.4)' },
}

export const AVATAR_STATES = {
  idle: { video: 'idle.mp4', label: 'Naira Idle' },
  listening: { video: 'listening.mp4', label: 'Naira Listening' },
  thinking: { video: 'thinking.mp4', label: 'Naira Thinking' },
  talking: { video: 'talking.mp4', label: 'Naira Speaking' },
  laughing: { video: 'laughing.mp4', label: 'Naira Laughing' },
}

const HALO_COLORS = {
  idle: { '--halo-1': '#a78bfa', '--halo-2': '#22d3ee', '--halo-3': '#f472b6' },
  listening: { '--halo-1': '#22d3ee', '--halo-2': '#38bdf8', '--halo-3': '#a78bfa' },
  thinking: { '--halo-1': '#60a5fa', '--halo-2': '#818cf8', '--halo-3': '#22d3ee' },
  talking: { '--halo-1': '#f472b6', '--halo-2': '#c084fc', '--halo-3': '#fb7185' },
  laughing: { '--halo-1': '#34d399', '--halo-2': '#a3e635', '--halo-3': '#22d3ee' },
}

export function AppProvider({ children }) {
  const [screen, setScreen] = useState('boot')
  const [profile, setProfile] = useState(() => {
    try {
      const raw = localStorage.getItem('naira.profile')
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })
  const [accent, setAccent] = useState(() => {
    try {
      return localStorage.getItem('naira.accent') || 'aurora'
    } catch {
      return 'aurora'
    }
  })
  const [toasts, setToasts] = useState([])
  const [avatarState, setAvatarState] = useState('idle')
  const [wsStatus, setWsStatus] = useState('connecting')

  const socketRef = useRef(null)
  const onMessageRef = useRef(null)

  useEffect(() => {
    const root = document.documentElement
    const vars = ACCENTS[accent] || ACCENTS.aurora
    Object.entries(vars).forEach(([k, v]) => root.style.setProperty(k, v))
    localStorage.setItem('naira.accent', accent)
  }, [accent])

  useEffect(() => {
    if (profile) localStorage.setItem('naira.profile', JSON.stringify(profile))
  }, [profile])

  const connect = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState <= WebSocket.OPEN) return
    setWsStatus('connecting')
    const ws = new WebSocket(WS_URL())
    socketRef.current = ws
    ws.onopen = () => setWsStatus('online')
    ws.onclose = () => {
      setWsStatus('offline')
      setTimeout(connect, 2500)
    }
    ws.onerror = () => ws.close()
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        onMessageRef.current?.(data)
      } catch {
        /* ignore malformed frames */
      }
    }
  }, [])

  const send = useCallback((payload) => {
    const ws = socketRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return false
    ws.send(typeof payload === 'string' ? payload : JSON.stringify(payload))
    return true
  }, [])

  const toast = useCallback((message, kind = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t, { id, message, kind }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3800)
  }, [])

  const value = useMemo(
    () => ({
      screen,
      setScreen,
      profile,
      setProfile,
      accent,
      setAccent,
      toasts,
      toast,
      avatarState,
      setAvatarState,
      wsStatus,
      connect,
      send,
      setOnMessage: (fn) => {
        onMessageRef.current = fn
      },
    }),
    [screen, profile, accent, toasts, toast, avatarState, wsStatus, connect, send]
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  return useContext(AppContext)
}

export { ACCENTS }
