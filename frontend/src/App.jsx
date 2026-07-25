import React, { useState } from 'react';
import BootScreen from './screens/Screen1_Boot/BootScreen';
import ApiVaultScreen from './screens/Screen2_ApiVault/ApiVaultScreen';
import HandshakeScreen from './screens/Screen3_Handshake/HandshakeScreen';
import DashboardScreen from './screens/Screen4_Dashboard/DashboardScreen';
import { useNairaStore } from './state/useNairaStore';

/**
 * Naira-OS Master App Router & State Manager
 * Centralized Auth Check: Boot -> (Auto-Bypass Vault if keys present) -> Handshake -> Dashboard
 */
function App() {
  const isHandshakeComplete = useNairaStore((state) => state.isHandshakeComplete);
  const setHandshakeComplete = useNairaStore((state) => state.setHandshakeComplete);
  const [currentScreen, setCurrentScreen] = useState('boot'); // 'boot' | 'api_vault' | 'handshake' | 'dashboard'

  // Centralized Synchronous Auth Check
  const checkHasKey = () => {
    const key =
      localStorage.getItem('naira_gemini_key') ||
      localStorage.getItem('gemini_api_key') ||
      localStorage.getItem('naira_opencode_key') ||
      localStorage.getItem('naira_opencode_zen_key') ||
      import.meta.env.VITE_GEMINI_API_KEY ||
      import.meta.env.VITE_OPENCODE_API_KEY ||
      import.meta.env.VITE_OPENCODE_ZEN_API_KEY;

    return Boolean(key && key.trim());
  };

  const handleBootComplete = () => {
    const hasKey = checkHasKey();
    const isHandshakeDone = isHandshakeComplete || localStorage.getItem('naira_handshake_done') === 'true';

    if (hasKey) {
      console.log('[NAIRA-OS] Centralized Auth Check: Valid API key found. Skipping API Vault.');
      if (isHandshakeDone) {
        setCurrentScreen('dashboard');
      } else {
        setCurrentScreen('handshake');
      }
    } else {
      console.log('[NAIRA-OS] Centralized Auth Check: No API Key found. Routing to API Vault.');
      setCurrentScreen('api_vault');
    }
  };

  const handleVaultProceed = () => {
    const isHandshakeDone = isHandshakeComplete || localStorage.getItem('naira_handshake_done') === 'true';
    if (isHandshakeDone) {
      setCurrentScreen('dashboard');
    } else {
      setCurrentScreen('handshake');
    }
  };

  return (
    <div className="relative w-screen h-screen bg-[#0A0E27] overflow-hidden flex flex-col">
      {/* Screen Render Router */}
      {currentScreen === 'boot' && (
        <BootScreen onBootComplete={handleBootComplete} />
      )}
      {currentScreen === 'api_vault' && (
        <ApiVaultScreen onProceed={handleVaultProceed} />
      )}
      {currentScreen === 'handshake' && (
        <HandshakeScreen
          onHandshakeComplete={() => {
            localStorage.setItem('naira_handshake_done', 'true');
            setHandshakeComplete(true);
            setCurrentScreen('dashboard');
          }}
        />
      )}
      {currentScreen === 'dashboard' && (
        <DashboardScreen />
      )}
    </div>
  );
}

export default App;
