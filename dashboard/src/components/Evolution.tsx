import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts'
import { Series, Point } from '../api'
import { C, fmt, statusColor } from './ui'

const clock = (s: number) => {
  const q = Math.min(Math.floor(s / 900) + 1, 5)
  const r = (q <= 4 ? 900 : 600) - (s - Math.min(q - 1, 4) * 900)
  return `Q${q} ${Math.floor(r / 60)}:${String(Math.round(r % 60)).padStart(2, '0')}`
}

export default function Evolution({ s, selected, onPick }: { s: Series; selected: number | null; onPick: (p: Point) => void }) {
  const move = (d: number) => {
    const i = s.points.findIndex(p => p.playId === selected)
    const n = s.points[Math.min(s.points.length - 1, Math.max(0, (i < 0 ? 0 : i) + d))]
    if (n) onPick(n)
  }
  const pts = s.points.filter(p => p.elapsed != null)
  const data = pts.map(p => ({ ...p, band: p.lo != null && p.hi != null ? [p.lo, p.hi] : null }))
  const withIdx = data.filter(d => d.index != null)
  const habit = s.summary.habit_pct ?? 0
  const lo = withIdx.length ? Math.min(40, Math.floor(Math.min(...withIdx.map(d => d.index!)) / 20) * 20) : 40
  const hi = withIdx.length ? Math.max(160, Math.ceil(Math.max(...withIdx.map(d => d.index!)) / 20) * 20) : 160
  const dom = [lo, hi]
  const yTicks: number[] = []
  for (let t = lo; t <= hi; t += 20) yTicks.push(t)
  const maxT = Math.max(...pts.map(p => p.elapsed!), 3600)

  const Dot = (props: any) => {
    const { cx, cy, payload } = props
    if (cx == null || cy == null) return <g />
    const p = payload as Point
    const sel = p.playId === selected
    const flag = p.status === 'caida_para_revisar' && p.evaluated
    const col = flag ? C.warn : p.comparable ? C.pt : 'none'
    const r = sel ? 7 : 5
    return (
      <g style={{ cursor: 'pointer' }} onClick={() => onPick(p)}>
        <circle cx={cx} cy={cy} r={12} fill="transparent" />
        {flag
          ? <polygon points={`${cx},${cy - r - 1} ${cx + r + 1},${cy + r} ${cx - r - 1},${cy + r}`} fill={col} stroke={sel ? '#fff' : C.bg} strokeWidth={sel ? 2 : 1.5} />
          : <circle cx={cx} cy={cy} r={r - 0.5} fill={col} stroke={p.comparable ? (sel ? '#fff' : C.bg) : C.mute} strokeWidth={sel ? 2 : 1.5} />}
        {sel && <circle cx={cx} cy={cy} r={r + 5} fill="none" stroke="#fff" strokeOpacity={0.6} strokeDasharray="2 2" />}
      </g>
    )
  }
  const Tip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null
    const p: Point = payload[0].payload
    return (
      <div className="rounded-lg border p-3 text-xs" style={{ background: C.bg, borderColor: C.line, color: C.text, maxWidth: 270 }}>
        <div className="mb-1 font-semibold">Intervención #{p.order} · {p.elapsed != null ? clock(p.elapsed) : ''} · jugada {p.playId}</div>
        <div className="mb-1" style={{ color: statusColor(p.status) }}>{p.evaluated ? (p.status === 'caida_para_revisar' ? '▲ Marca de revisión' : p.status === 'dentro_variacion' ? 'Dentro de su variación' : 'Evidencia insuficiente') : 'No evaluada (fuera de la regla)'}</div>
        <div>Índice: <b>{fmt(p.index, 0)}</b> · Rapidez 0–1 s: {fmt(p.v, 2)} yd/s</div>
        <div style={{ color: C.mute }}>Ref. {fmt(p.v_ref, 2)} yd/s · n={p.ref_n}, {p.ref_games} partidos</div>
        <div className="mt-1">{p.ctx.alineacion} · {p.ctx.down}&amp;{p.ctx.yardas_por_ganar} · {p.ctx.formacion_ofensiva}</div>
        <div>{p.ctx.cobertura} · rushers {p.ctx.n_rushers} · bloq. {p.ctx.bloqueadores_asignados}{p.ctx.play_action ? ' · play action' : ''}</div>
        <div className="mt-1" style={{ color: statusColor(p.status) }}>
          {p.excl_reason ? `Calidad: ${p.excl_reason}` : p.comparable ? 'Calidad: ventana completa (10 muestras)' : ''}
        </div>
        <div style={{ color: C.mute }}>Clic para abrir la jugada</div>
      </div>
    )
  }
  return (
    <div tabIndex={0} role="group" aria-label="Gráfica de evolución. Usa las flechas izquierda y derecha para cambiar de intervención; Inicio y Fin para ir a la primera o última."
      onKeyDown={e => { if (e.key === 'ArrowRight') { e.preventDefault(); move(1) } else if (e.key === 'ArrowLeft') { e.preventDefault(); move(-1) } else if (e.key === 'Home') { e.preventDefault(); move(-999) } else if (e.key === 'End') { e.preventDefault(); move(999) } }}
      className="rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-400">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs" style={{ color: C.mute }}>
        <button onClick={() => move(-1)} className="rounded border px-2 py-1 font-semibold" style={{ borderColor: C.line, color: C.text }} aria-label="Intervención anterior">◀ anterior</button>
        <button onClick={() => move(1)} className="rounded border px-2 py-1 font-semibold" style={{ borderColor: C.line, color: C.text }} aria-label="Intervención siguiente">siguiente ▶</button>
        <span>También con las flechas del teclado · clic en un punto abre su replay.</span>
      </div>
      <div style={{ width: '100%', height: 340 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke={C.line} strokeDasharray="3 3" />
            <XAxis type="number" dataKey="elapsed" domain={[0, maxT]} ticks={[0, 900, 1800, 2700, 3600].filter(t => t <= maxT)}
              tickFormatter={(t: number) => (t === 0 ? 'Inicio' : `Q${Math.min(t / 900 + 1, 5)}`)} stroke={C.mute} fontSize={11} />
            <YAxis domain={dom} ticks={yTicks} stroke={C.mute} fontSize={11} width={36} />
            {s.gaps.map((g, i) => (
              <ReferenceArea key={i} x1={g.start} x2={g.end} fill="#64748b" fillOpacity={0.16} stroke="#64748b" strokeDasharray="4 3" strokeOpacity={0.5}
                label={{ value: 'sin obs.', fill: C.mute, fontSize: 9, position: 'insideTop' }} />
            ))}
            <ReferenceArea y1={100 - habit} y2={100 + habit} fill={C.ok} fillOpacity={0.09} />
            <ReferenceLine y={100} stroke={C.ok} strokeWidth={1.5} label={{ value: 'Referencia propia = 100', fill: C.ok, fontSize: 10, position: 'insideTopRight' }} />
            <ReferenceLine y={100 - s.summary.threshold_pts} stroke={C.warn} strokeDasharray="5 4" strokeOpacity={0.7} label={{ value: 'umbral de revisión', fill: C.warn, fontSize: 10, position: 'insideBottomRight' }} />
            {[900, 1800, 2700].filter(t => t < maxT).map(t => <ReferenceLine key={t} x={t} stroke={C.line} />)}
            <Area dataKey="band" stroke="none" fill={C.pt} fillOpacity={0.15} connectNulls isAnimationActive={false} legendType="none" tooltipType="none" />
            <Line dataKey="trend" stroke={C.pt} strokeWidth={2.5} dot={false} connectNulls isAnimationActive={false} legendType="none" tooltipType="none" />
            <Scatter dataKey="index" shape={<Dot />} isAnimationActive={false} />
            <Tooltip content={<Tip />} cursor={{ stroke: C.line }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs" style={{ color: C.mute }}>
        <li><span style={{ color: C.pt }}>●</span> Intervención comparable</li>
        <li><span style={{ color: C.warn }}>▲</span> Marca de revisión (triángulo ámbar)</li>
        <li>○ Play action / no comparable (fuera de referencia y alertas)</li>
        <li><span style={{ color: C.pt }}>━</span> Tendencia suavizada ± incertidumbre (media móvil de {3}; {s.summary.mode === 'live' ? 'solo pasado' : 'centrada'})</li>
        <li><span style={{ color: C.ok }}>▭</span> Variación habitual (±{fmt(habit, 0)}%)</li>
        <li>▨ Sin observación como Pass Rush — <b>no</b> es descanso confirmado</li>
      </ul>
      <details className="mt-3 text-xs" style={{ color: C.mute }}>
        <summary className="cursor-pointer font-semibold" style={{ color: C.text }}>Ver como tabla (alternativa accesible)</summary>
        <div className="mt-2 max-h-72 overflow-auto">
          <table className="w-full text-left"><caption className="sr-only">Intervenciones del partido</caption>
            <thead><tr><th>#</th><th>Reloj</th><th>Jugada</th><th>Índice</th><th>Rapidez (yd/s)</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {s.points.map(p => (
                <tr key={p.playId} className="border-t" style={{ borderColor: C.line, background: p.playId === selected ? C.line : 'transparent' }}>
                  <td>{p.order}</td><td>Q{p.ctx.cuarto} {p.ctx.reloj}</td><td>{p.playId}</td><td>{fmt(p.index, 0)}</td><td>{fmt(p.v, 2)}</td>
                  <td>{!p.evaluated ? 'No evaluada' : p.status === 'caida_para_revisar' ? '▲ Marca' : p.status === 'dentro_variacion' ? 'Normal' : 'Insuficiente'}</td>
                  <td><button onClick={() => onPick(p)} className="rounded border px-2 py-0.5" style={{ borderColor: C.line, color: C.text }}>Abrir</button></td>
                </tr>))}
            </tbody></table>
        </div>
      </details>
    </div>
  )
}
