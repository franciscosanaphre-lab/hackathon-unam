import { useEffect, useRef, useState } from 'react'
import { AiCompareOut, Compare as Cmp, Mode, Point, post } from '../api'
import Field from './Field'
import { C, Card, fmt, Msg } from './ui'

export default function CompareView({ cmp, nflId, mode, points, refPlayId, onRef }: { cmp: Cmp; nflId: number; mode: Mode; points: Point[]; refPlayId: number | null; onRef: (p: number | null) => void }) {
  const [ai, setAi] = useState<{ key: string; r?: AiCompareOut; err?: string } | null>(null)
  const [aiBusy, setAiBusy] = useState(false)
  const k = `${nflId}-${cmp.selected.gameId}-${cmp.selected.point.playId}-${cmp.reference.point.playId}-${mode}`
  const curK = useRef(k); curK.current = k
  useEffect(() => { setAiBusy(false) }, [k])
  const explain = async () => {
    const kk = k; setAiBusy(true)
    try {
      const r = await post<AiCompareOut>('ai/compare-plays', { nflId, gameId: cmp.selected.gameId, playId: cmp.selected.point.playId, refGameId: cmp.reference.gameId, refPlayId: cmp.reference.point.playId, mode })
      if (curK.current === kk) setAi({ key: kk, r })
    } catch (e) { if (curK.current === kk) setAi({ key: kk, err: (e as Error).message }) }
    finally { if (curK.current === kk) setAiBusy(false) }
  }
  const aiNow = ai && ai.key === k ? ai : null
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
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs" style={{ color: C.mute }}>
        <label>Jugada de referencia
          <select value={refPlayId ?? ''} onChange={e => onRef(e.target.value ? Number(e.target.value) : null)} className="ml-1 rounded border bg-transparent px-1 py-1" style={{ borderColor: C.line, color: C.text }}>
            <option value="" style={{ background: C.bg }}>Automática (cercana a su mediana)</option>
            {points.filter(p => p.playId !== cmp.selected.point.playId).map(p => <option key={p.playId} value={p.playId} style={{ background: C.bg }}>#{p.order} · jugada {p.playId} · índice {fmt(p.index, 0)}</option>)}
          </select></label>
        <button onClick={explain} disabled={aiBusy} className="rounded-md px-3 py-1.5 font-bold disabled:opacity-60" style={{ background: C.ok, color: '#04210f' }}>{aiBusy ? 'Explicando…' : 'Explicar diferencias con IA'}</button>
      </div>
      {aiNow?.err && <div className="mt-2 rounded border px-3 py-2 text-xs" style={{ borderColor: C.warn, color: C.warn }}>La IA no está disponible: {aiNow.err}</div>}
      {aiNow?.r && <div className="mt-2 whitespace-pre-wrap rounded border px-3 py-2 text-sm" style={{ borderColor: C.line, background: '#081326', color: C.text }}>{aiNow.r.explanation.replace(/[#*]/g, '')}<div className="mt-1 text-[10px]" style={{ color: aiNow.r.numbers_verified ? C.ok : C.warn }}>{aiNow.r.numbers_verified ? 'Cifras verificadas contra el cálculo de Python' : 'Contiene cifras no verificadas'}</div></div>}
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
