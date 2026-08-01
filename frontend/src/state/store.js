import { useCallback, useEffect, useRef, useState } from 'react'

export function usePersistedState(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key)
      if (raw !== null) return JSON.parse(raw)
    } catch {
      /* ignore */
    }
    return typeof initial === 'function' ? initial() : initial
  })

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch {
      /* ignore */
    }
  }, [key, value])

  return [value, setValue]
}

export function makeId(prefix = 'id') {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

export function nowSec() {
  return Math.floor(Date.now() / 1000)
}

export function formatTime(ts) {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function formatDate(ts) {
  const d = new Date(ts)
  const today = new Date()
  const sameDay = d.toDateString() === today.toDateString()
  if (sameDay) return 'Today'
  const yest = new Date(today)
  yest.setDate(yest.getDate() - 1)
  if (d.toDateString() === yest.toDateString()) return 'Yesterday'
  return d.toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })
}

export function groupByDate(items, tsKey) {
  const groups = []
  for (const item of [...items].reverse()) {
    const label = formatDate(item[tsKey])
    const last = groups[groups.length - 1]
    if (last && last.label === label) last.items.push(item)
    else groups.push({ label, items: [item] })
  }
  return groups
}

export function useInterval(callback, delay) {
  const saved = useRef(callback)
  useEffect(() => {
    saved.current = callback
  }, [callback])
  useEffect(() => {
    if (delay === null) return
    const t = setInterval(() => saved.current(), delay)
    return () => clearInterval(t)
  }, [delay])
}

export function randomHex(bytes = 32) {
  const arr = new Uint8Array(bytes)
  crypto.getRandomValues(arr)
  return Array.from(arr, (b) => b.toString(16).padStart(2, '0')).join('')
}
