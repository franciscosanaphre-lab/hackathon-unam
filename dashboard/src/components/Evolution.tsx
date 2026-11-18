import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts'
import { Series, Point } from '../api'
import { C, fmt, statusColor } from './ui'

const clock = (s: number) => {
  const q = Math.min(Math.floor(s / 900) + 1, 5)
  const r = (q <= 4 ? 900 : 600) - (s - Math.min(q - 1, 4) * 900)
  return `Q${q} ${Math.floor(r / 60)}:${String(Math.round(r % 60)).padStart(2, '0')}`
}

export default function Evolution({ s, selected, onPick }: { s: Series; selected: number | null; onPick: (p: Point) => void }) {
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
    const flag = p.status === 'caida_para_revisar'
    const col = flag ? C.warn : p.comparable ? C.pt : 'none'
    return (
      <g style={{ cursor: 'pointer' }} onClick={() => onPick(p)}>
        <circle cx={cx} cy={cy} r={12} fill="transparent" />
        <circle cx={cx} cy={cy} r={sel ? 6.5 : 4.5} fill={col} stroke={p.comparable ? (sel ? '#fff' : C.bg) : C.mute} strokeWidth={sel ? 2 : 1.5} />
      </g>
    )
  }
  const Tip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null
    const p: Point = payload[0].payload
    return (
      <div className="rounded-lg border p-3 text-xs" style={{ background: C.bg, borderColor: C.line, color: C.text, maxWidth: 270 }}>
        <div className="mb-1 font-semibold">Intervención #{p.order} · {p.elapsed != null ? clock(p.elapsed) : ''}</div>
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
    <div>
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
        <li><span style={{ color: C.warn }}>●</span> Marca de revisión</li>
        <li>○ Play action / no comparable (fuera de referencia y alertas)</li>
        <li><span style={{ color: C.pt }}>━</span> Tendencia suavizada ± incertidumbre (media móvil de {3}; {s.summary.mode === 'live' ? 'solo pasado' : 'centrada'})</li>
        <li><span style={{ color: C.ok }}>▭</span> Variación habitual (±{fmt(habit, 0)}%)</li>
        <li>▨ Sin observación como Pass Rush — <b>no</b> es descanso confirmado</li>
      </ul>
    </div>
  )
}
