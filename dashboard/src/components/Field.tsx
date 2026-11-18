import { Replay } from '../api'
import { C } from './ui'

export const EVT: Record<string, string> = { ball_snap: 'snap', autoevent_ballsnap: 'snap (auto)', pass_forward: 'lanzamiento', autoevent_passforward: 'lanzamiento (auto)', qb_sack: 'sack', pass_arrived: 'llega el pase', pass_outcome_caught: 'pase completo', pass_outcome_incomplete: 'pase incompleto', line_set: 'línea lista', man_in_motion: 'hombre en movimiento', play_action: 'play action', run: 'carrera', fumble: 'fumble', autoevent_passinterrupted: 'pase interrumpido' }
export const evLabel = (e?: string) => (!e || e === 'None' ? '' : EVT[e] ?? e.replace(/_/g, ' '))

const lerp = (a: number, b: number, t: number) => a + (b - a) * t

/** Posición interpolada (solo visual) en frame relativo al snap (fraccionario). */
export function posAt(r: Replay, key: string, rel: number): [number, number, number | null] | null {
  const tr = r.tracks[key]
  if (!tr) return null
  const base = r.snap_frame != null ? r.frames.indexOf(r.snap_frame) : 0
  const f = Math.min(Math.max(base + rel, 0), r.frames.length - 1)
  const i0 = Math.floor(f), i1 = Math.min(i0 + 1, r.frames.length - 1), t = f - i0
  const a = tr[i0], b = tr[i1]
  if (!a || a[0] == null || a[1] == null) return null
  if (!b || b[0] == null || b[1] == null) return [a[0], a[1], a[2]]
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), a[2]]
}

export default function Field({ r, rel, title }: { r: Replay; rel: number; title: string }) {
  const los = r.los_x ?? 60
  const x0 = Math.max(0, los - 14), x1 = Math.min(120, los + 18)
  const W = x1 - x0
  const ballSnap = r.snap_frame != null ? r.tracks['ball']?.[r.frames.indexOf(r.snap_frame)] : null
  const tgt = r.players.find(p => p.target)
  const tp = tgt && r.snap_frame != null ? r.tracks[String(tgt.nflId)]?.[r.frames.indexOf(r.snap_frame)] : null
  const cy = tp?.[1] ?? ballSnap?.[1] ?? 26.65
  const H = 34
  const y0 = Math.min(Math.max(cy - H / 2, 0), 53.3 - H)
  const target = r.players.find(p => p.target)
  const base = r.snap_frame != null ? r.frames.indexOf(r.snap_frame) : 0
  const maxRel = r.frames.length - 1 - base
  const trail = (key: string, upto: number) => {
    const pts: string[] = []
    for (let k = 0; k <= Math.min(upto, maxRel); k++) { const p = posAt(r, key, k); if (p) pts.push(`${p[0]},${p[1]}`) }
    return pts.join(' ')
  }
  const win = r.window ? [r.window[0] - (r.snap_frame ?? 0), r.window[1] - (r.snap_frame ?? 0)] : null
  const curFrame = r.frames[Math.min(Math.max(Math.round(base + rel), 0), r.frames.length - 1)]
  const ev = r.events[String(curFrame)]
  const lines = []
  for (let x = Math.ceil((x0 - 10) / 5) * 5; x <= x1 - 10; x += 5) lines.push(x + 10)
  const ball = posAt(r, 'ball', rel)
  const inWin = win && rel >= win[0] - 0.01 && rel <= win[1] + 0.01
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs" style={{ color: C.mute }}>
        <b style={{ color: C.text }}>{title}</b>
        <span>frame {curFrame}{r.snap_frame != null ? ` · ${rel >= 0 ? '+' : '−'}${(Math.abs(rel) / r.fps).toFixed(2)} s desde el snap` : ' · sin snap'}{evLabel(ev) ? ` · ${evLabel(ev)}` : ''}</span>
      </div>
      <svg viewBox={`${x0} ${y0} ${W} ${H}`} className="w-full rounded-lg" style={{ background: '#0a2a1f', border: `1px solid ${C.line}` }}>
        {lines.map(x => <line key={x} x1={x} x2={x} y1={y0} y2={y0 + H} stroke="#fff" strokeOpacity={0.14} strokeWidth={0.15} />)}
        <line x1={los} x2={los} y1={y0} y2={y0 + H} stroke={C.pt} strokeWidth={0.35} strokeDasharray="1 1" />
        <text x={los + 0.6} y={y0 + 2.2} fontSize={1.5} fill={C.pt}>LOS (balón en el snap)</text>
        <text x={x1 - 1} y={y0 + H - 1} fontSize={1.5} fill="#fff" fillOpacity={0.55} textAnchor="end">ataque →</text>
        {target && <polyline points={trail(String(target.nflId), maxRel)} fill="none" stroke={C.warn} strokeOpacity={0.25} strokeWidth={0.35} />}
        {target && win && <polyline points={(() => { const a: string[] = []; for (let k = 0; k <= Math.min(win[1], rel); k++) { const p = posAt(r, String(target.nflId), k); if (p) a.push(`${p[0]},${p[1]}`) } return a.join(' ') })()} fill="none" stroke={C.warn} strokeWidth={0.7} />}
        {r.players.map(p => {
          const q = posAt(r, String(p.nflId), rel)
          if (!q) return null
          const def = p.team === r.defensive_team
          const col = def ? '#4f8cff' : C.off
          return (
            <g key={p.nflId}>
              {p.target && <circle cx={q[0]} cy={q[1]} r={1.8} fill="none" stroke={C.warn} strokeWidth={0.5} />}
              <circle cx={q[0]} cy={q[1]} r={p.target ? 1.1 : 0.8} fill={p.target ? C.warn : col} fillOpacity={p.target ? 1 : 0.85} />
              {p.target && <text x={q[0]} y={q[1] - 2.8} fontSize={1.5} fill={C.warn} textAnchor="middle">#{p.jersey}</text>}
            </g>
          )
        })}
        {ball && <ellipse cx={ball[0]} cy={ball[1]} rx={0.9} ry={0.55} fill="#c8803c" stroke="#fff" strokeWidth={0.15} />}
      </svg>
      <div className="mt-1 text-[11px]" style={{ color: C.mute }}>
        <span style={{ color: '#4f8cff' }}>●</span> defensa ({r.defensive_team}) · <span style={{ color: C.off }}>●</span> ataque · <span style={{ color: C.warn }}>●</span> defensivo analizado ·
        trayectoria gruesa = ventana de la métrica (snap → +1.0 s){inWin ? ' · dentro de la ventana' : ''}
      </div>
    </div>
  )
}
