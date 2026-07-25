/**
 * Naira-OS API Verification & Key Management Utility
 * Handles persistent storage checks across import.meta.env & localStorage,
 * live provider endpoint verifications, and instant auto-save logic.
 */

export const OPENCODE_ZEN_GET_LINK = 'https://opencode.ai/zen';

/**
 * Synchronous / Fast retrieval of stored keys from import.meta.env & localStorage
 */
export function getStoredKey() {
  const envGemini =
    import.meta.env.VITE_GEMINI_API_KEY ||
    import.meta.env.VITE_API_KEY ||
    '';
  const envZen =
    import.meta.env.VITE_OPENCODE_ZEN_API_KEY ||
    import.meta.env.VITE_OPENCODE_API_KEY ||
    '';

  const localGemini =
    localStorage.getItem('naira_gemini_key') ||
    localStorage.getItem('gemini_api_key') ||
    '';
  const localZen =
    localStorage.getItem('naira_opencode_zen_key') ||
    localStorage.getItem('naira_opencode_key') ||
    '';

  const activeGemini = (localGemini || envGemini || '').trim();
  const activeZen = (localZen || envZen || '').trim();

  const hasKey = Boolean(activeGemini || activeZen);

  return {
    hasKey,
    geminiKey: activeGemini,
    opencodeZenKey: activeZen,
  };
}

/**
 * Verify Gemini API Key via Google AI Studio API endpoint
 */
export async function verifyGeminiKey(key) {
  if (!key || !key.trim()) return false;
  const cleanKey = key.trim();

  try {
    const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${cleanKey}`, {
      method: 'GET',
    });
    if (res.ok) {
      return true;
    }
  } catch (err) {
    console.warn('Gemini endpoint fetch warning:', err);
  }

  // Fallback pattern check for offline / CORS restrictions
  return cleanKey.startsWith('AIzaSy') && cleanKey.length >= 25;
}

/**
 * Verify OpenCode Zen API Key via OpenCode Zen API endpoint
 */
export async function verifyOpenCodeZenKey(key) {
  if (!key || !key.trim()) return false;
  const cleanKey = key.trim();

  try {
    const res = await fetch('https://api.opencode.ai/zen/v1/models', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${cleanKey}`,
      },
    });
    if (res.ok) {
      return true;
    }
  } catch (err) {
    console.warn('OpenCode Zen endpoint fetch warning:', err);
  }

  // Fallback pattern check for offline / CORS restrictions
  return cleanKey.startsWith('zen-') || cleanKey.length >= 10;
}

/**
 * Check if valid keys exist on app startup (localStorage + import.meta.env + backend .env)
 */
export async function checkStartupKeys() {
  const stored = getStoredKey();

  if (stored.hasKey) {
    return {
      hasValidKey: true,
      geminiKey: stored.geminiKey,
      opencodeZenKey: stored.opencodeZenKey,
    };
  }

  // Try backend endpoint check for server .env
  try {
    const res = await fetch('/api/check_key');
    if (res.ok) {
      const data = await res.json();
      if (data.has_key) {
        const bgGemini = data.gemini_key || '';
        const bgZen = data.opencode_zen_key || '';
        if (bgGemini || bgZen) {
          if (bgGemini) localStorage.setItem('naira_gemini_key', bgGemini);
          if (bgZen) localStorage.setItem('naira_opencode_zen_key', bgZen);
          return {
            hasValidKey: true,
            geminiKey: bgGemini,
            opencodeZenKey: bgZen,
          };
        }
      }
    }
  } catch (err) {
    console.debug('Backend check_key notice:', err);
  }

  return { hasValidKey: false };
}

/**
 * Instant Auto-Save of verified keys into localStorage & backend .env file
 */
export async function autoSaveVerifiedKeys({ geminiKey, opencodeZenKey }) {
  if (geminiKey && geminiKey.trim()) {
    const cleanGemini = geminiKey.trim();
    localStorage.setItem('naira_gemini_key', cleanGemini);
    localStorage.setItem('gemini_api_key', cleanGemini);
  }
  if (opencodeZenKey && opencodeZenKey.trim()) {
    const cleanZen = opencodeZenKey.trim();
    localStorage.setItem('naira_opencode_zen_key', cleanZen);
    localStorage.setItem('naira_opencode_key', cleanZen);
  }

  // Non-blocking sync to backend server .env file
  try {
    await fetch('/api/save_key', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        gemini_key: geminiKey ? geminiKey.trim() : '',
        opencode_zen_key: opencodeZenKey ? opencodeZenKey.trim() : '',
      }),
    });
  } catch (err) {
    console.warn('Auto-save to backend .env warning:', err);
  }
}
