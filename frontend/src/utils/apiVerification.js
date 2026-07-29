export const OPENCODE_ZEN_GET_LINK = 'https://opencode.ai/zen';
export const API_BASE = (import.meta.env.VITE_API_BASE || 'http://localhost:8000').replace(/\/$/, '');

async function readErrorMessage(response) {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return body.detail;
    if (typeof body?.message === 'string') return body.message;
  } catch (_) {
    // A proxy or server failure can return HTML instead of JSON.
  }
  return `Backend error: ${response.status} ${response.statusText}`;
}

export async function saveVaultConfiguration({ provider, apiKey }) {
  const cleanKey = typeof apiKey === 'string' ? apiKey.trim() : '';
  if (!cleanKey) throw new Error('An API key is required before it can be verified.');

  try {
    const response = await fetch(`${API_BASE}/api/settings/vault`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ provider, api_key: cleanKey }),
    });
    if (!response.ok) throw new Error(await readErrorMessage(response));
    return await response.json();
  } catch (error) {
    if (error?.name === 'TypeError' || error?.message?.includes('Failed to fetch')) {
      throw new Error(`Cannot connect to Backend (${API_BASE}). Ensure FastAPI is running.`);
    }
    throw error;
  }
}

export async function getVaultStatus() {
  try {
    const response = await fetch(`${API_BASE}/api/settings/status`, {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) return { configured: false };
    return await response.json();
  } catch (_) {
    return { configured: false };
  }
}

// Legacy compatibility stubs for any older callers.
export async function checkStartupKeys() {
  const status = await getVaultStatus();
  return { hasValidKey: status.configured, geminiKey: '', opencodeZenKey: '' };
}

export const getStoredKey = () => ({ hasKey: false, geminiKey: '', opencodeZenKey: '' });
export const verifyGeminiKey = async () => false;
export const verifyOpenCodeZenKey = async () => false;
export const autoSaveVerifiedKeys = async () => {};
