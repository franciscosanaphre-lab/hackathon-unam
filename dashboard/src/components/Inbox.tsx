import { Inbox as InboxT, InboxItem } from '../api'
import { C, fmt } from './ui'

export default function InboxPanel({ data, loading, error, onOpen }: { data: InboxT | null; loading: boolean; error: string; onOpen: (i: InboxItem) => void }) {
  return (
    <details open className="rounded-xl border p-3" style={{ background: C.panel, borderColor: C.line }}>
      <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Bandeja de revisión del equipo {data && <span className="normal-case tracking-normal">· {data.items.filter(i => i.kind === 'marca').length} con marca</span>}</summary>
      <div className="mt-3">
        {loading && <p className="text-sm" style={{ color: C.mute }}>⏳ Calculando secuencias del equipo…</p>}
        {error && <p className="text-sm" style={{ color: C.warn }}>⚠ {error}</p>}
        {data && !loading && data.items.length === 0 && <p className="text-sm" style={{ color: C.mute }}>Ningún jugador evaluable tiene una secuencia que cumpla la regla ni se acerque al umbral en este partido. Eso es un resultado válido, no un fallo.</p>}
        {data && !loading && data.items.length > 0 && (
          <ul className="max-h-44 space-y-2 overflow-y-auto pr-1">
            {data.items.map(i => (
              <li key={`${i.nflId}-${i.playId}`} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm" style={{ borderColor: i.kind === 'marca' ? C.warn : C.line, background: '#081326' }}>
                <div>
                  <span className="mr-2 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase" style={{ border: `1px solid ${i.kind === 'marca' ? C.warn : C.mute}`, color: i.kind === 'marca' ? C.warn : C.mute }}>{i.kind === 'marca' ? '▲ Cumple la regla' : 'Cerca del umbral'}</span>
                  <b>{i.name}</b> <span style={{ color: C.mute }}>({i.pos})</span>
                  <div className="text-xs" style={{ color: C.mute }}>{i.n_plays} jugadas seguidas · {i.reloj} · índice medio {fmt(i.mean_index, 0)}{i.retro_also === false ? ' · no se repite en retrospectivo' : ''}</div>
                </div>
                <button onClick={() => onOpen(i)} className="rounded-md border px-3 py-1.5 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-sky-400" style={{ borderColor: C.ok, color: C.ok }}>Abrir ▶</button>
              </li>))}
          </ul>
        )}
        {data && <details className="mt-2 text-[11px]" style={{ color: C.mute }}><summary className="cursor-pointer">Cómo se ordena</summary><p className="mt-1">{data.order_rule} Evaluados: {data.evaluated}; sin evidencia suficiente: {data.insufficient}.</p></details>}
      </div>
    </details>
  )
}
