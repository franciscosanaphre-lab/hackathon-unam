import { ReactNode } from 'react'

export const C = { bg: '#050d1c', panel: '#0b1a33', line: '#1c2f52', text: '#e6edf8', mute: '#8ea2c4', ok: '#34d399', warn: '#fbbf24', pt: '#7fb4ff', off: '#cbd5e1' }

export function Card({ title, sub, children, right }: { title: string; sub?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="rounded-xl border p-4" style={{ background: C.panel, borderColor: C.line }}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ color: C.mute }}>{title}</h2>
          {sub && <p className="mt-0.5 text-xs" style={{ color: C.mute }}>{sub}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  )
}

export const Msg = ({ kind, children }: { kind: 'load' | 'err' | 'empty'; children: ReactNode }) => (
  <div className="rounded-lg border px-4 py-6 text-center text-sm" style={{ borderColor: C.line, color: kind === 'err' ? C.warn : C.mute }}>
    {kind === 'load' ? '⏳ ' : kind === 'err' ? '⚠ ' : ''}{children}
  </div>
)

export const statusColor = (s: string) => (s === 'caida_para_revisar' ? C.warn : s === 'dentro_variacion' ? C.ok : C.mute)

export function Pill({ status, label }: { status: string; label: string }) {
  const c = statusColor(status)
  return <span className="inline-block rounded-full border px-3 py-1 text-xs font-semibold" style={{ color: c, borderColor: c }}>{label}</span>
}

export const fmt = (v: number | null | undefined, d = 1) => (v == null ? '—' : v.toFixed(d))
