import { useEffect, useState } from 'react'
import { Puzzle, Plus, Trash2, Upload, Wand2, Power, Loader2 } from 'lucide-react'
import { SectionShell, GlassCard, Toggle, Modal, EmptyState } from '../components/ui.jsx'
import { useApp } from '../state/AppContext.jsx'
import { usePersistedState, makeId } from '../state/store.js'
import { getCapabilities, setCapabilityEnabled } from '../api/client.js'

const CAP_META = {
  llm: { label: 'LLM Engine', desc: 'Gemini / DeepSeek reasoning core' },
  memory: { label: 'Memory Engine', desc: 'Relation, context aur semantic engines' },
  vision: { label: 'Vision', desc: 'Screen dekh ke samajhna (Gemini Vision)' },
  voice: { label: 'Voice Studio', desc: 'RVC voice conversion + TTS' },
  browser: { label: 'Browser', desc: 'Chrome tabs, search, navigation' },
  pc_control: { label: 'PC Control', desc: 'System commands, apps, volume, lock' },
  file_manager: { label: 'File Manager', desc: 'Files aur folders manage karo' },
  security: { label: 'Security', desc: 'Permission engine aur request validation' },
  coding_agent: { label: 'Coding Agent', desc: 'Autonomous development tasks' },
  avatar_3d: { label: '3D Avatar', desc: '3D avatar rendering' },
}

export default function PluginsSection({ onClose }) {
  const { toast } = useApp()
  const [caps, setCaps] = useState([])
  const [loading, setLoading] = useState(true)
  const [skills, setSkills] = usePersistedState('naira.skills', [])
  const [builderOpen, setBuilderOpen] = useState(false)
  const [skillForm, setSkillForm] = useState({ name: '', desc: '', steps: '' })

  const loadCaps = async () => {
    setLoading(true)
    try {
      const res = await getCapabilities()
      if (res && Array.isArray(res.capabilities)) setCaps(res.capabilities)
    } catch (err) {
      toast(err.message || 'Capabilities load nahi hui', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCaps()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const toggleCap = async (cap, v) => {
    const prev = caps.map((c) => (c.name === cap.name ? { ...c, enabled: v } : c))
    setCaps(prev)
    try {
      await setCapabilityEnabled(cap.name, v)
      toast(`${CAP_META[cap.name]?.label || cap.name} ${v ? 'enabled' : 'disabled'}`, v ? 'success' : 'info')
    } catch (err) {
      setCaps(caps.map((c) => (c.name === cap.name ? { ...c, enabled: !v } : c)))
      toast(err.message || 'Toggle failed — backend reject kar raha hai', 'error')
    }
  }

  const saveSkill = () => {
    if (!skillForm.name.trim()) return
    setSkills((s) => [
      {
        id: makeId('skill'),
        name: skillForm.name.trim(),
        desc: skillForm.desc.trim(),
        steps: skillForm.steps.split('\n').filter(Boolean),
        createdAt: Date.now(),
      },
      ...s,
    ])
    setSkillForm({ name: '', desc: '', steps: '' })
    setBuilderOpen(false)
    toast(`Skill "${skillForm.name}" saved`, 'success')
  }

  return (
    <SectionShell icon={<Puzzle size={18} />} title="Plugins & Skills" subtitle="Extend Naira ki powers" onClose={onClose}>
      <div className="between" style={{ marginBottom: -4 }}>
        <div className="tiny">Installed Capabilities</div>
        <button className="btn btn-ghost btn-tiny" onClick={loadCaps} disabled={loading} title="Refresh">
          <Loader2 size={12} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>
      {loading ? (
        <div className="glass-soft" style={{ padding: 24, textAlign: 'center' }}>
          <Loader2 size={20} className="spin" style={{ color: 'var(--accent-1)' }} />
        </div>
      ) : caps.length === 0 ? (
        <EmptyState icon={<Power size={30} />} title="Koi capability nahi mili" note="Backend offline hai ya koi capability register nahi hui. Refresh dabao." />
      ) : (
        caps.map((cap) => {
          const meta = CAP_META[cap.name] || { label: cap.name, desc: cap.description || 'Registered capability' }
          return (
            <GlassCard key={cap.name} className="card">
              <div className="between">
                <div className="row" style={{ gap: 12 }}>
                  <div style={{ width: 36, height: 36, borderRadius: 11, display: 'grid', placeItems: 'center', background: cap.enabled ? 'rgba(52,211,153,0.13)' : 'rgba(167,139,250,0.13)', color: cap.enabled ? 'var(--mint)' : 'var(--violet)', flexShrink: 0 }}>
                    <Power size={16} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13.5 }}>{meta.label}</div>
                    <div className="tiny" style={{ marginTop: 3, textTransform: 'none', letterSpacing: 0 }}>{meta.desc}</div>
                  </div>
                </div>
                <Toggle checked={cap.enabled} onChange={(v) => toggleCap(cap, v)} />
              </div>
            </GlassCard>
          )
        })
      )}

      <div className="between" style={{ marginTop: 6 }}>
        <div className="tiny">Custom Skills ({skills.length})</div>
        <button className="btn btn-primary btn-sm" onClick={() => setBuilderOpen(true)}>
          <Plus size={14} /> Skill Builder
        </button>
      </div>

      {skills.length === 0 ? (
        <EmptyState icon={<Wand2 size={30} />} title="Koi skill nahi bani" note="Skill Builder se apni custom skill banao — upload ya create karke." />
      ) : (
        skills.map((s) => (
          <GlassCard key={s.id} className="card">
            <div className="between">
              <div className="row" style={{ gap: 10 }}>
                <div style={{ width: 36, height: 36, borderRadius: 11, display: 'grid', placeItems: 'center', background: 'rgba(34,211,238,0.13)', color: 'var(--cyan)', flexShrink: 0 }}>
                  <Wand2 size={16} />
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13.5 }}>{s.name}</div>
                  <div className="tiny" style={{ marginTop: 3, textTransform: 'none', letterSpacing: 0 }}>{s.desc || 'No description'}</div>
                </div>
              </div>
              <button className="btn btn-ghost btn-tiny" onClick={() => setSkills((list) => list.filter((x) => x.id !== s.id))}>
                <Trash2 size={12} />
              </button>
            </div>
            {s.steps.length > 0 && (
              <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 5 }}>
                {s.steps.map((st, i) => (
                  <div key={i} className="row" style={{ gap: 8, fontSize: 12, color: 'var(--text-2)' }}>
                    <span style={{ color: 'var(--accent-2)', fontFamily: 'monospace' }}>{i + 1}.</span> {st}
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        ))
      )}

      <button className="btn btn-ghost btn-sm" style={{ borderStyle: 'dashed' }}>
        <Upload size={14} /> Upload skill file (.json)
      </button>

      <SkillBuilder
        open={builderOpen}
        form={skillForm}
        setForm={setSkillForm}
        onClose={() => setBuilderOpen(false)}
        onSave={saveSkill}
      />
    </SectionShell>
  )
}

function SkillBuilder({ open, form, setForm, onClose, onSave }) {
  return (
    <Modal open={open} onClose={onClose} title="Create a skill">
      <div className="field-group">
        <label className="field-label">Skill Name</label>
        <input className="field" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. WhatsApp Message Sender" />
      </div>
      <div className="field-group">
        <label className="field-label">Description</label>
        <input className="field" value={form.desc} onChange={(e) => setForm((f) => ({ ...f, desc: e.target.value }))} placeholder="Ye skill kya karti hai?" />
      </div>
      <div className="field-group">
        <label className="field-label">Steps (ek line mein ek)</label>
        <textarea className="field" rows={5} value={form.steps} onChange={(e) => setForm((f) => ({ ...f, steps: e.target.value }))} placeholder={'1. Contact pick karo\n2. Message type karo\n3. Send dabao'} style={{ resize: 'none' }} />
      </div>
      <button className="btn btn-primary" style={{ width: '100%' }} disabled={!form.name.trim()} onClick={onSave}>
        <Wand2 size={15} /> Save skill
      </button>
    </Modal>
  )
}
