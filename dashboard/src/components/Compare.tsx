import { useEffect, useRef, useState } from 'react'
import { Compare as Cmp } from '../api'
import Field from './Field'
import { C, Card, fmt, Msg } from './ui'

export default function CompareView({ cmp }: { cmp: Cmp }) {
  const a = cmp.reference.replay, b = cmp.selected.replay
  const sa = a.snap_frame != null ? a.frames.indexOf(a.snap_frame) : 0
  const sb = b.snap_frame != null ? b.frames.indexOf(b.snap_frame) : 0
  const minRel = -Math.min(sa, sb)
  const maxRel = Math.min(a.frames.length - 1 - sa, b.frames.length - 1 - sb)
  const [rel, setRel] = useState(0)
  const [play, setPlay] = useState(false)
  const [speed, setSpeed] = useState(0.5)
  const last = useRef<number>(0)
  useEffect(() => { setRel(0); setPlay(false) }, [cmp])
  useEffect(() => {
    if (!play) return
    let id = 0
    last.current = performance.now()
    const tick = (t: number) => {
      const dt = (t - last.current) / 1000; last.current = t
      setRel(r => { const n = r + dt * 10 * speed; if (n >= maxRel) { setPlay(false); return maxRel } return n })
      id = requestAnimationFrame(tick)
    }
    id = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(id)
  }, [play, speed, maxRel])
  const synced = a.snap_frame != null && b.snap_frame != null
  const step = (d: number) => { setPlay(false); setRel(r => Math.min(maxRel, Math.max(minRel, Math.round(r) + d))) }
  const btn = 'rounded-md border px-3 py-1 text-xs font-semibold hover:bg-white/5'
  return (
    <Card title="Comparador de replays" sub={synced ? 'Sincronizado en ball_snap (evento común). Interpolación solo visual; las métricas usan las muestras originales a 10 fps.' : 'Falta snap en una jugada: no hay sincronización común.'}>
      {cmp.warnings.map(w => <div key={w} className="mb-2 rounded border px-3 py-1.5 text-xs" style={{ borderColor: C.warn, color: C.warn }}>⚠ {w}</div>)}
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <Field r={a} rel={rel} title={`Referencia · ${cmp.reference_auto ? 'auto' : 'elegida'} · índice ${fmt(cmp.reference.point.v != null && cmp.selected.point.v_ref ? 100 * cmp.reference.point.v / cmp.selected.point.v_ref : null, 0)} (vs ref. de la jugada seleccionada) · ${fmt(cmp.reference.point.v, 2)} yd/s`} />
          <p className="mt-1 text-xs" style={{ color: C.mute }}>{a.description}</p>
        </div>
        <div>
          <Field r={b} rel={rel} title={`Seleccionada · índice ${fmt(cmp.selected.point.index, 0)} · ${fmt(cmp.selected.point.v, 2)} yd/s`} />
          <p className="mt-1 text-xs" style={{ color: C.mute }}>{b.description}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2" style={{ color: C.text }}>
        <button className={btn} style={{ borderColor: C.line }} onClick={() => step(-1)} aria-label="Frame anterior">◀ frame</button>
        <button className={btn} style={{ borderColor: C.ok, color: C.ok }} onClick={() => { if (rel >= maxRel) setRel(0); setPlay(p => !p) }}>{play ? '⏸ Pausa' : '▶ Reproducir'}</button>
        <button className={btn} style={{ borderColor: C.line }} onClick={() => step(1)} aria-label="Frame siguiente">frame ▶</button>
        <button className={btn} style={{ borderColor: C.line }} onClick={() => { setPlay(false); setRel(0) }}>Ir al snap</button>
        <label className="ml-2 text-xs" style={{ color: C.mute }}>Velocidad
          <select value={speed} onChange={e => setSpeed(Number(e.target.value))} className="ml-1 rounded border bg-transparent px-1 py-0.5" style={{ borderColor: C.line, color: C.text }}>
            {[0.1, 0.25, 0.5, 1].map(v => <option key={v} value={v} style={{ background: C.bg }}>{v}×</option>)}
          </select>
        </label>
        <input type="range" min={minRel} max={maxRel} step={0.1} value={rel} onChange={e => { setPlay(false); setRel(Number(e.target.value)) }} className="min-w-[160px] flex-1" aria-label="Frame relativo al snap" />
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead style={{ color: C.mute }}><tr><th className="py-1">Contexto</th><th>Referencia</th><th>Seleccionada</th></tr></thead>
          <tbody>
            {cmp.context.map(r => (
              <tr key={r.campo} className="border-t" style={{ borderColor: C.line }}>
                <td className="py-1" style={{ color: C.mute }}>{r.campo}</td>
                <td>{String(r.referencia ?? '—')}</td>
                <td style={{ color: r.difiere ? C.warn : C.text }}>{String(r.seleccionada ?? '—')}{r.difiere ? ' ≠' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-[11px]" style={{ color: C.mute }}>Criterio de referencia automática: {cmp.reference_rule}</p>
      </div>
    </Card>
  )
}
export { Msg }
