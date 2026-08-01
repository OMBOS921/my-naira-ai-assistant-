import { Canvas, useFrame } from '@react-three/fiber'
import { Float, Sparkles } from '@react-three/drei'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'

function ParticleField({ count = 1400 }) {
  const ref = useRef()
  const { positions, colors } = useMemo(() => {
    const pos = new Float32Array(count * 3)
    const col = new Float32Array(count * 3)
    const palette = [new THREE.Color('#22d3ee'), new THREE.Color('#a78bfa'), new THREE.Color('#f472b6'), new THREE.Color('#60a5fa')]
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 34
      pos[i * 3 + 1] = (Math.random() - 0.5) * 22
      pos[i * 3 + 2] = (Math.random() - 0.5) * 20
      const c = palette[Math.floor(Math.random() * palette.length)]
      const a = 0.35 + Math.random() * 0.6
      col[i * 3] = c.r * a
      col[i * 3 + 1] = c.g * a
      col[i * 3 + 2] = c.b * a
    }
    return { positions: pos, colors: col }
  }, [count])

  useFrame((_, delta) => {
    if (!ref.current) return
    ref.current.rotation.y += delta * 0.02
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.05} vertexColors transparent opacity={0.85} depthWrite={false} sizeAttenuation />
    </points>
  )
}

function AuroraOrb() {
  const ref = useRef()
  useFrame((state) => {
    if (!ref.current) return
    ref.current.rotation.z = state.clock.elapsedTime * 0.05
  })
  return (
    <group ref={ref}>
      <mesh position={[6, 3, -6]}>
        <sphereGeometry args={[2.4, 48, 48]} />
        <meshBasicMaterial color="#a78bfa" transparent opacity={0.07} />
      </mesh>
      <mesh position={[-7, -2, -8]}>
        <sphereGeometry args={[3.2, 48, 48]} />
        <meshBasicMaterial color="#22d3ee" transparent opacity={0.05} />
      </mesh>
      <mesh position={[0, 7, -12]}>
        <sphereGeometry args={[4.5, 48, 48]} />
        <meshBasicMaterial color="#f472b6" transparent opacity={0.035} />
      </mesh>
    </group>
  )
}

function RingTorus() {
  return (
    <Float speed={1.6} rotationIntensity={0.7} floatIntensity={1.2}>
      <mesh position={[0, 0, -9]} rotation={[Math.PI / 2.4, 0.4, 0]}>
        <torusGeometry args={[4.2, 0.02, 16, 120]} />
        <meshBasicMaterial color="#22d3ee" transparent opacity={0.25} />
      </mesh>
      <mesh position={[0, 0, -9]} rotation={[Math.PI / 2.4, 2.2, 0.4]}>
        <torusGeometry args={[5.2, 0.014, 16, 120]} />
        <meshBasicMaterial color="#a78bfa" transparent opacity={0.18} />
      </mesh>
    </Float>
  )
}

export default function Background3D({ interactive = false }) {
  return (
    <div className="scene-3d" style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: interactive ? 'auto' : 'none' }}>
      <Canvas camera={{ position: [0, 0, 10], fov: 55 }} dpr={[1, 1.6]} gl={{ antialias: true, alpha: true }}>
        <AuroraOrb />
        <ParticleField />
        <RingTorus />
        <Sparkles count={70} scale={[18, 12, 10]} size={2.4} speed={0.35} color="#7dd3fc" opacity={0.5} />
      </Canvas>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'radial-gradient(1000px 600px at 50% 42%, transparent 30%, rgba(7,11,30,0.55) 100%)',
          pointerEvents: 'none',
        }}
      />
    </div>
  )
}
