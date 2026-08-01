const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  let data = null
  const text = await res.text()
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text }
  }
  if (!res.ok) {
    const detail =
      (data && (data.detail || data.message)) ||
      (data && typeof data.detail === 'string' ? data.detail : null) ||
      `Request failed (${res.status})`
    const err = new Error(typeof detail === 'string' ? detail : 'Request failed')
    err.status = res.status
    throw err
  }
  return data
}

export async function getVaultStatus() {
  try {
    return await request('/api/settings/status')
  } catch {
    return { configured: false, reachable: false }
  }
}

export async function saveVaultConfiguration({ provider, apiKey, model }) {
  return request('/api/settings/vault', {
    method: 'POST',
    body: JSON.stringify({ provider, api_key: apiKey, model: model || undefined }),
  })
}

export async function getRemoteBridgeStatus() {
  try {
    return await request('/api/remote/status')
  } catch {
    return { reachable: false, connected: false, queue_size: 0, fcm_ready: false }
  }
}

export async function getCapabilities() {
  try {
    return await request('/api/capabilities')
  } catch {
    return { capabilities: [], reachable: false }
  }
}

export async function setCapabilityEnabled(name, enabled) {
  return request(`/api/capabilities/${name}/toggle`, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
}

export async function chatText(text, sessionId = 'default') {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ text, session_id: sessionId, modality: 'text' }),
  })
}

export const WS_URL = () => {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/naira`
}
