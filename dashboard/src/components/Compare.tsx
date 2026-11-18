import { useEffect, useRef, useState } from 'react'
import { AiCompareOut, Compare as Cmp, Mode, Point, Replay, post } from '../api'
import Field from './Field'
import { C, Card, fmt, statusColor } from './ui'

const show = (v: unknown) => (v === null || v === undefined || v === 'None' ? '—' : v === true ? 'Sí' : v === false ? 'No' : String(v))
const qColor = (n: string) => (n === 'alta' ? C.ok : n === 'media' ? C.warn : C.warn)
const qIcon = (n: string) => (n === 'alta' ? '●●●' : n === 'media' ? '●●○' : '●○○')

/** Replays sincronizados al snap. `ref` puede faltar (sin referencia comparable): se conserva el replay seleccionado. */
export default function CompareView({ cmp, single, nflId, mode, points, refPlayId, onRef }: {
  cmp?: Cmp; single?: { point: Point; replay: Replay; message: string }; nflId: number; mode: Mode; points: Point[]; refPlayId: number | null; onRef: (p: number | null) => void
}) {
  const a = cmp?.reference.replay, b = (cmp?.selected.replay ?? single?.replay)!
  const fps = b.fps
  const base = (r?: Replay) => (r && r.snap_frame != null ? r.frames.indexOf(r.snap_frame) : 0)
  const sa = base(a), sb = base(b)
  const minRel = -Math.min(...[sa, sb].filter((_, i) => (i === 0 ? !!a : true)))
  const maxRel = Math.min(...[a ? a.frames.length - 1 - sa : Infinity, b.frames.length - 1 - sb])
  const WIN = 10
  const [rel, setRel] = useState(0)
  const [play, setPlay] = useState(false)
  const [speed, setSpeed] = useState(0.5)
  const last = useRef(0)
  const sig = `${cmp?.selected.point.playId ?? single?.point.playId}-${cmp?.reference.point.playId ?? 'x'}-${mode}`
  useEffect(() => { setRel(0); setPlay(false) }, [sig])             // reinicia al cambiar de jugada/modo/referencia
  useEffect(() => { setRel(r => Math.min(Math.max(r, minRel), maxRel)) }, [minRel, maxRel])
  useEffect(() => {
    if (!play) return
    let id = 0
    last.current = performance.now()
    const tick = (t: number) => {
      const dt = (t - last.current) / 1000; last.current = t
      setRel(r => { const n = r + dt * fps * speed; if (n >= maxRel) { setPlay(false); return maxRel } return n })
      id = requestAnimationFrame(tick)
    }
    id = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(id)
  }, [play, speed, maxRel, fps])
  const step = (d: number) => { setPlay(false); setRel(r => Math.min(maxRel, Math.max(minRel, Math.round(r) + d))) }
  const synced = (!a || a.snap_frame != null) && b.snap_frame != null
  const btn = 'rounded-md border px-3 py-1.5 text-xs font-semibold hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-sky-400'

  // IA: explicar diferencias
  const [ai, setAi] = useState<{ key: string; r?: AiCompareOut; err?: string } | null>(null)
  const [aiBusy, setAiBusy] = useState(false)
  const k = `${nflId}-${cmp?.selected.gameId}-${cmp?.selected.point.playId}-${cmp?.reference.point.playId}-${mode}`
  const curK = useRef(k); curK.current = k
  useEffect(() => { setAiBusy(false) }, [k])
  const explain = async () => {
    if (!cmp) return
    const kk = k; setAiBusy(true)
    try {
      const r = await post<AiCompareOut>('ai/compare-plays', { nflId, gameId: cmp.selected.gameId, playId: cmp.selected.point.playId, refGameId: cmp.reference.gameId, refPlayId: cmp.reference.point.playId, mode })
      if (curK.current === kk) setAi({ key: kk, r })
    } catch (e) { if (curK.current === kk) setAi({ key: kk, err: (e as Error).message }) }
    finally { if (curK.current === kk) setAiBusy(false) }
  }
  const aiNow = ai && ai.key === k ? ai : null
  const selPt = cmp?.selected.point ?? single!.point
  const pct = (x: number) => `${((x - minRel) / Math.max(maxRel - minRel, 1)) * 100}%`

  return (
    <Card title="Comparador de replays" sub={synced ? 'Ambas jugadas sincronizadas en el snap (evento común). Interpolación solo visual; las métricas usan las 10 muestras originales a 10 fps (0.1 s cada una).' : 'Falta snap en una jugada: no hay sincronización común.'}>
      {single && <div className="mb-2 rounded border px-3 py-2 text-xs" style={{ borderColor: C.warn, color: C.warn }}>⚠ {single.message} Se muestra solo el replay de la jugada seleccionada.</div>}
      {cmp?.warnings.map(w => <div key={w} className="mb-2 rounded border px-3 py-1.5 text-xs" style={{ borderColor: C.warn, color: C.warn }}>⚠ {w}</div>)}

      <div className="rounded-lg border p-2" style={{ borderColor: C.line, background: '#081326' }}>
        <div className="flex flex-wrap items-center gap-2">
          <button className={btn} style={{ borderColor: C.line }} onClick={() => step(-1)} aria-label="Retroceder un frame (0.1 s)">◀ −1 frame</button>
          <button className={btn} style={{ borderColor: C.ok, color: C.ok }} onClick={() => { if (rel >= maxRel) setRel(0); setPlay(p => !p) }}>{play ? '⏸ Pausa' : '▶ Reproducir'}</button>
          <button className={btn} style={{ borderColor: C.line }} onClick={() => step(1)} aria-label="Avanzar un frame (0.1 s)">+1 frame ▶</button>
          <button className={btn} style={{ borderColor: C.line }} onClick={() => { setPlay(false); setRel(0) }}>Ir al snap</button>
          <label className="text-xs" style={{ color: C.mute }}>Velocidad de reproducción
            <select value={speed} onChange={e => setSpeed(Number(e.target.value))} className="ml-1 rounded border bg-transparent px-1 py-1" style={{ borderColor: C.line, color: C.text }}>
              {[0.1, 0.25, 0.5, 1].map(v => <option key={v} value={v} style={{ background: C.bg }}>{v}× (1× = tiempo real)</option>)}
            </select></label>
          <span className="ml-auto text-xs font-semibold" style={{ color: C.text }}>{rel >= 0 ? '+' : '−'}{(Math.abs(rel) / fps).toFixed(2)} s desde el snap</span>
        </div>
        <div className="relative mt-2 px-1">
          <div className="pointer-events-none absolute top-1/2 h-3 -translate-y-1/2 rounded" style={{ left: pct(0), width: `calc(${pct(Math.min(WIN, maxRel))} - ${pct(0)})`, background: C.warn, opacity: 0.35 }} aria-hidden />
          <input type="range" min={minRel} max={maxRel} step={0.1} value={rel} onChange={e => { setPlay(false); setRel(Number(e.target.value)) }} className="relative w-full" aria-label="Posición en frames relativos al snap" />
        </div>
        <div className="mt-0.5 text-[11px]" style={{ color: C.mute }}>
          <span style={{ color: C.warn }}>▬</span> Ventana de la métrica: snap → +1.0 s (10 muestras: frames snap+1 … snap+10; el desplazamiento usa además el frame del snap). Eje: {(minRel / fps).toFixed(1)} s … +{(maxRel / fps).toFixed(1)} s.
        </div>
      </div>

      <div className="mt-3 grid gap-4 lg:grid-cols-2">
        {a && cmp && (
          <div>
            <Field r={a} rel={rel} title={`Referencia · jugada ${a.playId} · ${fmt(cmp.reference.point.v, 2)} yd/s · índice ${fmt(cmp.reference.point.index_vs_ref_propia, 0)}`} />
            <p className="mt-1 text-xs" style={{ color: C.mute }}>{a.description}</p>
          </div>
        )}
        <div>
          <Field r={b} rel={rel} title={`Seleccionada · jugada ${b.playId} · ${fmt(selPt.v, 2)} yd/s · índice ${fmt(selPt.index, 0)}`} />
          <p className="mt-1 text-xs" style={{ color: C.mute }}>{b.description}</p>
        </div>
      </div>

      {cmp && (<>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs" style={{ color: C.mute }}>
          <label>Jugada de referencia
            <select value={refPlayId ?? ''} onChange={e => onRef(e.target.value ? Number(e.target.value) : null)} className="ml-1 rounded border bg-transparent px-1 py-1" style={{ borderColor: C.line, color: C.text }}>
              <option value="" style={{ background: C.bg }}>Automática (contexto más parecido)</option>
              {points.filter(p => p.playId !== cmp.selected.point.playId).map(p => <option key={p.playId} value={p.playId} style={{ background: C.bg }}>#{p.order} · jugada {p.playId} · Q{p.ctx.cuarto} {p.ctx.reloj} · índice {fmt(p.index, 0)}</option>)}
            </select></label>
          <button onClick={explain} disabled={aiBusy} className="rounded-md px-3 py-1.5 font-bold disabled:opacity-60" style={{ background: C.ok, color: '#04210f' }}>{aiBusy ? 'Explicando…' : 'Explicar diferencias con IA'}</button>
        </div>
        {aiNow?.err && <div className="mt-2 rounded border px-3 py-2 text-xs" style={{ borderColor: C.warn, color: C.warn }}>La IA no está disponible: {aiNow.err}</div>}
        {aiNow?.r && <div className="mt-2 whitespace-pre-wrap rounded border px-3 py-2 text-sm" style={{ borderColor: C.line, background: '#081326', color: C.text }}>{aiNow.r.explanation.replace(/[#*]/g, '')}<div className="mt-1 text-[10px]" style={{ color: aiNow.r.numbers_verified ? C.ok : C.warn }}>{aiNow.r.numbers_verified ? 'Cifras verificadas contra el cálculo de Python' : 'Contiene cifras no verificadas'}</div></div>}

        <div className="mt-4 rounded-lg border p-3" style={{ borderColor: qColor(cmp.quality.nivel), background: '#081326' }}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-semibold">Calidad de la comparación: <span style={{ color: qColor(cmp.quality.nivel) }}>{qIcon(cmp.quality.nivel)} {cmp.quality.nivel.toUpperCase()}</span></div>
            <div className="text-xs" style={{ color: C.mute }}>{cmp.reference_auto ? `Selección automática entre ${cmp.match_info.n_candidatas} candidatas${cmp.match_info.solo_pasado ? ' (solo jugadas previas)' : ''}` : 'Referencia elegida manualmente'}</div>
          </div>
          <p className="mt-1 text-xs" style={{ color: C.mute }}>{cmp.quality.regla}</p>
          <p className="mt-1 text-xs" style={{ color: C.mute }}>Criterio: {cmp.reference_rule}</p>
        </div>

        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Diferencias de contexto entre la jugada de referencia y la seleccionada</caption>
            <thead style={{ color: C.mute }}><tr><th className="py-1">Contexto</th><th>Referencia</th><th>Seleccionada</th><th className="w-24">¿Difiere?</th></tr></thead>
            <tbody>
              {cmp.context.map(r => (
                <tr key={r.campo} className="border-t" style={{ borderColor: C.line }}>
                  <td className="py-1" style={{ color: C.mute }}>{r.campo}</td>
                  <td>{show(r.referencia)}</td>
                  <td style={{ color: r.difiere ? C.warn : C.text }}>{show(r.seleccionada)}</td>
                  <td style={{ color: r.difiere ? C.warn : C.mute }}>{r.difiere ? '▲ Difiere' : 'Igual'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>)}
    </Card>
  )
}
export { statusColor }
