import { useEffect, useRef } from 'react'

/**
 * useSpatialAudio hook for JARVIS-style 3D sound positioning.
 * Automatically pans audio based on UI context (e.g. speaking from center,
 * proactive notifications from right, system errors from left).
 */
export function useSpatialAudio() {
  const audioCtxRef = useRef(null)
  const masterGainRef = useRef(null)

  useEffect(() => {
    // Initialize Web Audio API on first user interaction
    const initAudio = () => {
      if (!audioCtxRef.current) {
        const AudioContext = window.AudioContext || window.webkitAudioContext
        audioCtxRef.current = new AudioContext()
        masterGainRef.current = audioCtxRef.current.createGain()
        masterGainRef.current.connect(audioCtxRef.current.destination)
      }
      if (audioCtxRef.current.state === 'suspended') {
        audioCtxRef.current.resume()
      }
    }

    window.addEventListener('click', initAudio, { once: true })
    window.addEventListener('keydown', initAudio, { once: true })
    return () => {
      window.removeEventListener('click', initAudio)
      window.removeEventListener('keydown', initAudio)
    }
  }, [])

  /**
   * Play base64 audio with spatial positioning.
   * @param {string} base64Audio 
   * @param {Object} options { panX: -1 to 1, panY: -1 to 1, volume: 0 to 1 }
   */
  const playSpatial = async (base64Audio, options = {}) => {
    if (!base64Audio) return
    const { panX = 0, panY = 0, volume = 1.0 } = options

    try {
      const ctx = audioCtxRef.current
      if (!ctx) {
        // Fallback to standard audio if context not initialized
        const audio = new Audio('data:audio/wav;base64,' + base64Audio)
        audio.volume = volume
        audio.play().catch(console.error)
        return
      }

      // Convert base64 to array buffer
      const binaryStr = window.atob(base64Audio)
      const len = binaryStr.length
      const bytes = new Uint8Array(len)
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryStr.charCodeAt(i)
      }
      const buffer = bytes.buffer

      // Decode audio
      const audioBuffer = await ctx.decodeAudioData(buffer)

      // Setup source
      const source = ctx.createBufferSource()
      source.buffer = audioBuffer

      // Setup panner
      const panner = ctx.createPanner()
      panner.panningModel = 'HRTF' // High quality 3D spatialization
      panner.distanceModel = 'inverse'
      panner.refDistance = 1
      panner.maxDistance = 10000
      panner.rolloffFactor = 1

      // Position the audio (X, Y, Z)
      // Z is negative to sound like it's coming from in front of the screen
      panner.positionX.value = panX * 5 
      panner.positionY.value = panY * 5
      panner.positionZ.value = -3 

      // Setup gain (volume)
      const gainNode = ctx.createGain()
      gainNode.gain.value = volume

      // Connect nodes: source -> panner -> gain -> master
      source.connect(panner)
      panner.connect(gainNode)
      gainNode.connect(masterGainRef.current)

      source.start(0)
    } catch (err) {
      console.error('[SpatialAudio] Playback failed:', err)
      // Fallback
      const audio = new Audio('data:audio/wav;base64,' + base64Audio)
      audio.play().catch(console.error)
    }
  }

  return { playSpatial }
}
