import React, { useCallback, useEffect, useState } from 'react';
import BootScreen from './screens/Screen1_Boot/BootScreen';
import ApiVaultScreen from './screens/Screen2_ApiVault/ApiVaultScreen';
import HandshakeScreen from './screens/Screen3_Handshake/HandshakeScreen';
import DashboardScreen from './screens/Screen4_Dashboard/DashboardScreen';
import { useNairaStore } from './state/useNairaStore';
import { getVaultStatus } from './utils/apiVerification';

function App() {
  const setHandshakeComplete = useNairaStore((state) => state.setHandshakeComplete);
  const [currentScreen, setCurrentScreen] = useState('boot');

  // This is the only startup vault check.  It is deliberately mount-only:
  // a screen transition must never trigger another credential check.
  useEffect(() => {
    let cancelled = false;

    const resolveStartupScreen = async () => {
      const status = await getVaultStatus();
      if (cancelled) return;

      const isHandshakeDone =
        useNairaStore.getState().isHandshakeComplete ||
        localStorage.getItem('naira_handshake_done') === 'true';
      const nextScreen = status.configured
        ? (isHandshakeDone ? 'dashboard' : 'handshake')
        : 'api_vault';

      setCurrentScreen((screen) => (screen === nextScreen ? screen : nextScreen));
    };

    void resolveStartupScreen();
    return () => { cancelled = true; };
  }, []);

  // Fallback only if the boot animation completes before the mount-time
  // status request.  It cannot re-route an already selected screen.
  const handleBootComplete = useCallback(() => {
    setCurrentScreen((screen) => (screen === 'boot' ? 'api_vault' : screen));
  }, []);

  const handleVaultProceed = useCallback(() => {
    const isHandshakeDone =
      useNairaStore.getState().isHandshakeComplete ||
      localStorage.getItem('naira_handshake_done') === 'true';
    setCurrentScreen(isHandshakeDone ? 'dashboard' : 'handshake');
  }, []);

  const handleHandshakeComplete = useCallback(() => {
    localStorage.setItem('naira_handshake_done', 'true');
    setHandshakeComplete(true);
    setCurrentScreen('dashboard');
  }, [setHandshakeComplete]);

  return (
    <div className="relative w-screen h-screen bg-[#0A0E27] overflow-hidden flex flex-col">
      {currentScreen === 'boot' && <BootScreen onBootComplete={handleBootComplete} />}
      {currentScreen === 'api_vault' && <ApiVaultScreen onProceed={handleVaultProceed} />}
      {currentScreen === 'handshake' && <HandshakeScreen onHandshakeComplete={handleHandshakeComplete} />}
      {currentScreen === 'dashboard' && <DashboardScreen />}
    </div>
  );
}

export default App;
