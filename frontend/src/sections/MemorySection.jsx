import { useState } from 'react'
import { Brain, Plus, Trash2, Search, Tag, User, Pencil } from 'lucide-react'
import { SectionShell, GlassCard, EmptyState, Modal } from '../components/ui.jsx'
import { useApp } from '../state/AppContext.jsx'
import { usePersistedState, makeId } from '../state/store.js'

const SEED_MEMORIES = [
  { id: 'seed_1', title: 'Operator Profile', detail: 'Handshake se bhari hui basic details — naam, language, tone.', tags: ['profile'], pinned: true },
]

export default function MemorySection({ onClose }) {
  const { profile } = useApp()
  const [memories, setMemories] = usePersistedState('naira.memories', SEED_MEMORIES)
  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState(null)

  const profileMemories = profile
    ? [
        { title: 'Name', value: profile.name, key: 'name' },
        { title: 'Language', value: profile.language, key: 'language' },
        { title: 'Tone', value: profile.tone, key: 'tone' },
        { title: 'Wake Word', value: profile.wakeWord, key: 'wakeWord' },
        { title: 'PC Name', value: profile.pcName || '—', key: 'pcName' },
        { title: 'Role', value: profile.role || '—', key: 'role' },
      ]
    : []

  const filtered = memories.filter(
    (m) =>
      !query ||
      m.title.toLowerCase().includes(query.toLowerCase()) ||
      m.detail.toLowerCase().includes(query.toLowerCase()) ||
      m.tags.some((t) => t.toLowerCase().includes(query.toLowerCase()))
  )

  return (
    <SectionShell icon={<Brain size={18} />} title="Memory" subtitle="Jo Naira aapke baare mein jaanti hai" onClose={onClose}>
      <div className="row" style={{ position: 'relative' }}>
        <Search size={15} style={{ position: 'absolute', left: 14, color: 'var(--text-3)', zIndex: 1 }} />
        <input className="field" placeholder="Memory search karo..." value={query} onChange={(e) => setQuery(e.target.value)} style={{ paddingLeft: 38 }} />
      </div>

      <div>
        <div className="tiny" style={{ marginBottom: 10 }}>Handshake Profile</div>
        <div className="grid-2">
          {profileMemories.map((p) => (
            <div key={p.key} className="glass-soft" style={{ padding: '11px 13px' }}>
              <div className="tiny" style={{ textTransform: 'none', letterSpacing: 0 }}>{p.title}</div>
              <div style={{ fontSize: 13, fontWeight: 700, marginTop: 4, color: 'var(--text-1)' }}>{p.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="between">
        <div className="tiny">{memories.length} saved memories</div>
        <button className="btn btn-primary btn-sm" onClick={() => setEditing({ id: null, title: '', detail: '', tags: [] })}>
          <Plus size={14} /> Add memory
        </button>
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={<Brain size={30} />} title="Koi memory nahi mili" note="Handshake mein kuch miss hua toh yahan add kar sakte ho." />
      ) : (
        filtered.map((m) => (
          <GlassCard key={m.id} className="card">
            <div className="between">
              <div className="row" style={{ gap: 8 }}>
                <Tag size={13} style={{ color: 'var(--accent-2)' }} />
                <div style={{ fontWeight: 700, fontSize: 13.5 }}>{m.title}</div>
              </div>
              <div className="row" style={{ gap: 4 }}>
                <button className="btn btn-ghost btn-tiny" onClick={() => setEditing(m)}><Pencil size={11} /></button>
                <button
                  className="btn btn-ghost btn-tiny"
                  onClick={() => setMemories((list) => list.filter((x) => x.id !== m.id))}
                >
                  <Trash2 size={11} />
                </button>
              </div>
            </div>
            <div className="muted" style={{ fontSize: 12.5, lineHeight: 1.6, marginTop: 8 }}>{m.detail}</div>
            <div className="row" style={{ marginTop: 10, flexWrap: 'wrap', gap: 6 }}>
              {m.tags.map((t) => (
                <span key={t} className="badge badge-gray" style={{ textTransform: 'none', letterSpacing: 0 }}>#{t}</span>
              ))}
            </div>
          </GlassCard>
        ))
      )}

      <MemoryModal
        editing={editing}
        onClose={() => setEditing(null)}
        onSave={(data) => {
          if (editing?.id) {
            setMemories((list) => list.map((m) => (m.id === editing.id ? { ...m, ...data } : m)))
          } else {
            setMemories((list) => [{ id: makeId('mem'), ...data, pinned: false }, ...list])
          }
          setEditing(null)
        }}
      />
    </SectionShell>
  )
}

function MemoryModal({ editing, onClose, onSave }) {
  const [form, setForm] = useState(() => ({
    title: editing?.title || '',
    detail: editing?.detail || '',
    tags: editing?.tags.join(', ') || '',
  }))
  if (!editing) return null

  return (
    <Modal open={!!editing} onClose={onClose} title={editing.id ? 'Edit memory' : 'New memory'}>
      <div className="field-group">
        <label className="field-label">Title</label>
        <input className="field" value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="e.g. Meri favourite chai" />
      </div>
      <div className="field-group">
        <label className="field-label">Detail</label>
        <textarea className="field" rows={4} value={form.detail} onChange={(e) => setForm((f) => ({ ...f, detail: e.target.value }))} placeholder="Jo bhi Naira ko yaad rakhna ho..." style={{ resize: 'none' }} />
      </div>
      <div className="field-group">
        <label className="field-label">Tags (comma separated)</label>
        <input className="field" value={form.tags} onChange={(e) => setForm((f) => ({ ...f, tags: e.target.value }))} placeholder="personal, work, food" />
      </div>
      <button
        className="btn btn-primary"
        style={{ width: '100%' }}
        disabled={!form.title.trim()}
        onClick={() => onSave({ title: form.title.trim(), detail: form.detail.trim(), tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean) })}
      >
        Save memory
      </button>
    </Modal>
  )
}
