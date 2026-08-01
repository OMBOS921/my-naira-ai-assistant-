import { useEffect, useMemo, useRef } from 'react'
import { motion } from 'framer-motion'
import { useApp } from '../state/AppContext.jsx'

export default function AvatarStage({ size = 'lg', state = 'idle', children }) {
  const { avatarState: globalState } = useApp()
  const videoRef = useRef(null)
  const active = state === 'custom' ? globalState : state
  const stateKey = active === 'custom' ? globalState : active

  const videoFile = useMemo(() => {
    switch (stateKey) {
      case 'listening':
        return 'listening.mp4'
      case 'thinking':
        return 'thinking.mp4'
      case 'talking':
        return 'talking.mp4'
      case 'laughing':
        return 'laughing.mp4'
      default:
        return 'idle.mp4'
    }
  }, [stateKey])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const src = `/assets/${videoFile}`
    if (video.getAttribute('src') !== src) {
      video.setAttribute('src', src)
      video.load()
      video.play().catch(() => {})
    } else if (video.paused) {
      video.play().catch(() => {})
    }
  }, [videoFile])

  const halo = {
    idle: { '--halo-1': '#a78bfa', '--halo-2': '#22d3ee', '--halo-3': '#f472b6' },
    listening: { '--halo-1': '#22d3ee', '--halo-2': '#38bdf8', '--halo-3': '#a78bfa' },
    thinking: { '--halo-1': '#60a5fa', '--halo-2': '#818cf8', '--halo-3': '#22d3ee' },
    talking: { '--halo-1': '#f472b6', '--halo-2': '#c084fc', '--halo-3': '#fb7185' },
    laughing: { '--halo-1': '#34d399', '--halo-2': '#a3e635', '--halo-3': '#22d3ee' },
  }[stateKey]

  return (
    <motion.div
      className="avatar-stage"
      initial={{ opacity: 0, scale: 0.86 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="avatar-orb-wrap" style={halo}>
        <div className="avatar-glow" />
        <div className="avatar-halo" />
        <video
          ref={videoRef}
          className={`avatar-video ${size}`}
          autoPlay
          loop
          muted
          playsInline
          src="/assets/idle.mp4"
        />
      </div>
      {children}
    </motion.div>
  )
}
