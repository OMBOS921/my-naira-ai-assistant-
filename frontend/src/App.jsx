import { AnimatePresence, motion } from 'framer-motion'
import { AppProvider, useApp } from './state/AppContext.jsx'
import BootScreen from './screens/BootScreen.jsx'
import ApiVaultScreen from './screens/ApiVaultScreen.jsx'
import HandshakeScreen from './screens/HandshakeScreen.jsx'
import DashboardScreen from './screens/DashboardScreen.jsx'

function Screens() {
  const { screen, toasts } = useApp()

  return (
    <>
      <AnimatePresence mode="wait">
        <motion.div
          key={screen}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          style={{ position: 'absolute', inset: 0 }}
        >
          {screen === 'boot' && <BootScreen />}
          {screen === 'vault' && <ApiVaultScreen />}
          {screen === 'handshake' && <HandshakeScreen />}
          {screen === 'dashboard' && <DashboardScreen />}
        </motion.div>
      </AnimatePresence>

      <div className="toast-wrap">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              className={`toast ${t.kind}`}
              initial={{ opacity: 0, y: -18, scale: 0.94 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -12, scale: 0.96 }}
              transition={{ type: 'spring', stiffness: 360, damping: 30 }}
            >
              {t.message}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </>
  )
}

export default function App() {
  return (
    <AppProvider>
      <Screens />
    </AppProvider>
  )
}
