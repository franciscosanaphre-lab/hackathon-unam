import { useEffect, useMemo, useRef, useState } from 'react'
import { api, Compare, Demo, Game, Inbox, InboxItem, Mode, NoRef, PlayerItem, Point, Sensitivity, Series, Status } from './api'
import AIPanel from './components/AIPanel'
import ChatDrawer from './components/ChatDrawer'
import CompareView from './components/Compare'
import Evolution from './components/Evolution'
import InboxPanel from './components/Inbox'
import { C, Card, fmt, Msg, Pill, statusColor } from './components/ui'

const sel = 'rounded-md border bg-transparent px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400'
type Pending = { nflId: number; playId?: number | null }
type Demos = Partial<Record<Demo['kind'], Demo>>
const stLabel = (p: Point) => (!p.evaluated ? 'No evaluada (play action, ventana incompleta o sin referencia)' : p.status === 'caida_para_revisar' ? '▲ Caída observada para revisar' : p.status === 'dentro_variacion' ? 'Dentro de su variación habitual' : 'Evidencia insuficiente')

export default function App() {
  const [ready, setReady] = useState<'load' | 'ok' | 'err'>('load')
  const [err, setErr] = useState('')
  const [games, setGames] = useState<Game[]>([])
  const [gameId, setGameId] = useState<number | null>(null)
  const [team, setTeam] = useState<string>('')
  const [players, setPlayers] = useState<PlayerItem[] | null>(null)
  const [nflId, setNflId] = useState<number | null>(null)
  const [mode, setMode] = useState<Mode>('live')
  const [series, setSeries] = useState<Series | null>(null)
  const [sLoad, setSLoad] = useState(false)
  const [sErr, setSErr] = useState('')
  const [playId, setPlayId] = useState<number | null>(null)
  const [cmp, setCmp] = useState<Compare | null>(null)
  const [noRef, setNoRef] = useState<NoRef | null>(null)
  const [cLoad, setCLoad] = useState(false)
  const [cErr, setCErr] = useState('')
  const [refPlayId, setRefPlayId] = useState<number | null>(null)
  const [sens, setSens] = useState<Sensitivity | null>(null)
  const [demos, setDemos] = useState<Demos>({})
  const [demoKind, setDemoKind] = useState<Demo['kind'] | null>(null)
  const [pending, setPending] = useState<Pending | null>(null)
  const [inbox, setInbox] = useState<Inbox | null>(null)
  const [iLoad, setILoad] = useState(false)
  const [iErr, setIErr] = useState('')
  const playRef = useRef<number | null>(null); playRef.current = playId
  const pendingRef = useRef<Pending | null>(null); pendingRef.current = pending

  // Espera al backend; los casos demo se preparan un poco después
  useEffect(() => {
    let stop = false
    const poll = async () => {
      try {
        const s = await api<Status>('status')
        if (s.error) { setErr(s.error); setReady('err'); return }
        if (!s.ready) { if (!stop) setTimeout(poll, 1500); return }
        const g = await api<Game[]>('games')
        if (stop) return
        setGames(g); setReady('ok')
        if (g.length) { setGameId(g[0].gameId); setTeam(g[0].teams[0]) }
        const pollDemo = async () => {
          try { const d = await api<Demos>('demo-cases'); if (!stop) setDemos(d) } catch { if (!stop) setTimeout(pollDemo, 2000) }
        }
        pollDemo()
      } catch (e) { if (!stop) { setErr((e as Error).message); setReady('err') } }
    }
    poll()
    return () => { stop = true }
  }, [])

  const game = games.find(g => g.gameId === gameId)

  useEffect(() => {
    if (gameId == null || !team) return
    let off = false
    setPlayers(null)
    api<PlayerItem[]>(`games/${gameId}/teams/${team}/players`).then(p => {
      if (off) return
      setPlayers(p)
      setNflId(n => (pendingRef.current ? pendingRef.current.nflId : n != null && p.some(x => x.nflId === n) ? n : (p.find(x => x.evaluable) ?? p[0])?.nflId ?? null))
    }).catch(() => { if (!off) { setPlayers([]); setNflId(null) } })
    return () => { off = true }
  }, [gameId, team])

  // Bandeja de revisión (una consulta por partido/equipo/modo)
  useEffect(() => {
    if (gameId == null || !team) return
    let off = false
    setILoad(true); setIErr(''); setInbox(null)
    api<Inbox>(`games/${gameId}/teams/${team}/review-inbox?mode=${mode}`).then(r => { if (!off) setInbox(r) }).catch(e => { if (!off) setIErr((e as Error).message) }).finally(() => { if (!off) setILoad(false) })
    return () => { off = true }
  }, [gameId, team, mode])

  useEffect(() => {
    if (nflId == null || gameId == null) { setSeries(null); return }
    let off = false
    setSLoad(true); setSErr(''); setSeries(null); setCmp(null); setNoRef(null); setSens(null)
    api<Series>(`players/${nflId}/games/${gameId}/series?mode=${mode}`).then(s => {
      if (off) return
      setSeries(s)
      const keep = s.points.some(p => p.playId === playRef.current) ? playRef.current : null
      const pend = pendingRef.current?.playId
      const first = s.summary.first_flag_playId
      const pick = (pend && s.points.some(p => p.playId === pend) ? pend : null) ?? keep ?? first ?? s.points[s.points.length - 1]?.playId ?? null
      setPlayId(pick); setPending(null)
    }).catch(e => { if (!off) { setSeries(null); setSErr((e as Error).message) } }).finally(() => { if (!off) setSLoad(false) })
    api<Sensitivity>(`players/${nflId}/games/${gameId}/sensitivity`).then(x => { if (!off) setSens(x) }).catch(() => { if (!off) setSens(null) })
    return () => { off = true }
  }, [nflId, gameId, mode])

  useEffect(() => { setRefPlayId(null) }, [nflId, gameId])

  useEffect(() => {
    if (nflId == null || gameId == null || playId == null) return
    let off = false
    setCLoad(true); setCErr(''); setCmp(null); setNoRef(null)
    api<Compare | NoRef>(`compare?nflId=${nflId}&gameId=${gameId}&playId=${playId}&mode=${mode}${refPlayId ? `&refGameId=${gameId}&refPlayId=${refPlayId}` : ''}`).then(r => {
      if (off) return
      if ('error' in r) setNoRef(r); else setCmp(r)
    }).catch(e => { if (!off) setCErr((e as Error).message) }).finally(() => { if (!off) setCLoad(false) })
    return () => { off = true }
  }, [nflId, gameId, playId, mode, refPlayId])

  const activateDemo = (k: Demo['kind']) => {      // determinista: siempre el mismo estado inicial
    const d = demos[k]; if (!d) return
    setDemoKind(k); setMode('live'); setRefPlayId(null)
    setPending({ nflId: d.nflId, playId: d.playId }); pendingRef.current = { nflId: d.nflId, playId: d.playId }
    setGameId(d.gameId); setTeam(d.team); setNflId(d.nflId); setPlayId(d.playId)
  }
  const autoRef = useRef(false)
  useEffect(() => { if (!autoRef.current && demos.signal && !pendingRef.current) { autoRef.current = true; activateDemo('signal') } }, [demos]) // eslint-disable-line
  const openPlay = (p: number) => { setRefPlayId(null); setPlayId(p); document.getElementById('comparador')?.scrollIntoView({ behavior: 'smooth' }) }
  const openInbox = (i: InboxItem) => { setDemoKind(null); setPending({ nflId: i.nflId, playId: i.playId }); setNflId(i.nflId); setPlayId(i.playId) }

  const fresh = series && !sLoad && series.player.nflId === nflId && series.game.gameId === gameId && series.summary.mode === mode
  const s = fresh ? series!.summary : null
  const player = players?.find(p => p.nflId === nflId)
  const flagged = useMemo(() => series?.points.filter(p => p.status === 'caida_para_revisar' && p.evaluated) ?? [], [series])
  const selPoint = fresh ? series!.points.find(p => p.playId === playId) ?? null : null
  const cmpOk = cmp && cmp.selected.point.playId === playId && cmp.selected.gameId === gameId ? cmp : null
  const noRefOk = noRef && noRef.selected_only && noRef.selected_only.point.playId === playId ? noRef : null
  const demo = demoKind ? demos[demoKind] : undefined
  const demoActive = !!demo && demo.nflId === nflId && demo.gameId === gameId

  if (ready === 'load') return <Shell><Msg kind="load">El servidor está calculando las métricas sobre los datos de tracking (≈10 s)…</Msg></Shell>
  if (ready === 'err') return <Shell><Msg kind="err">No se pudieron cargar los datos: {err}</Msg></Shell>

  return (
    <Shell>
      <Card title="Selección" right={
        <div role="group" aria-label="Modo temporal" className="flex gap-1 rounded-lg border p-0.5 text-xs" style={{ borderColor: C.line }}>
          {(['live', 'retro'] as Mode[]).map(m => (
            <button key={m} onClick={() => setMode(m)} aria-pressed={mode === m} className="rounded-md px-3 py-1.5 font-semibold" style={{ background: mode === m ? C.line : 'transparent', color: mode === m ? C.text : C.mute }}>
              {m === 'live' ? 'En ese momento' : 'Retrospectivo'}
            </button>))}
        </div>}>
        <div className="flex flex-wrap items-end gap-3 text-xs" style={{ color: C.mute }}>
          <label>Partido<br />
            <select className={sel} style={{ borderColor: C.line, color: C.text }} value={gameId ?? ''} onChange={e => { const g = games.find(x => x.gameId === Number(e.target.value))!; setPending(null); setDemoKind(null); setGameId(g.gameId); setTeam(g.teams[0]) }}>
              {games.map(g => <option key={g.gameId} value={g.gameId} style={{ background: C.bg }}>S{g.week} · {g.away} @ {g.home} ({g.date})</option>)}
            </select></label>
          <label>Equipo (defensa)<br />
            <select className={sel} style={{ borderColor: C.line, color: C.text }} value={team} onChange={e => { setPending(null); setDemoKind(null); setTeam(e.target.value) }}>
              {(game?.teams ?? []).map(t => <option key={t} style={{ background: C.bg }}>{t}</option>)}
            </select></label>
          <label>Defensivo (rol Pass Rush)<br />
            <select className={sel} style={{ borderColor: C.line, color: C.text, minWidth: 240 }} value={nflId ?? ''} onChange={e => { setPending(null); setDemoKind(null); setNflId(Number(e.target.value)) }}>
              {(players ?? []).map(p => <option key={p.nflId} value={p.nflId} style={{ background: C.bg }}>{p.name} ({p.pos}) · {p.n_obs} obs{p.evaluable ? '' : ' · pocas'}</option>)}
            </select></label>
          <div className="flex flex-wrap items-end gap-2">
            {(['signal', 'normal', 'context'] as const).map(k => demos[k] && (
              <button key={k} onClick={() => activateDemo(k)} title={demos[k]!.criterio} className="rounded-md border px-3 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-sky-400" style={{ borderColor: C.ok, color: C.ok, background: demoKind === k ? '#0f3b2b' : 'transparent' }}>
                {k === 'signal' ? 'Caso demo: señal' : k === 'normal' ? 'Caso: variación normal' : 'Caso: contexto'}
              </button>))}
            {Object.keys(demos).length === 0 && <span className="text-[11px]">Preparando casos demo…</span>}
            {demoKind && <button onClick={() => activateDemo(demoKind)} className="rounded-md border px-2 py-1.5 text-[11px]" style={{ borderColor: C.line, color: C.mute }}>↺ Reiniciar</button>}
          </div>
        </div>
        <p className="mt-2 text-xs" style={{ color: C.mute }}>
          <b style={{ color: C.text }}>{mode === 'live' ? 'En ese momento:' : 'Retrospectivo:'}</b> {mode === 'live' ? 'referencia, umbral, suavizado y comparación automática usan solo intervenciones anteriores a cada punto; la referencia crece con el partido.' : 'la referencia es fija (toda su historia del dataset, incluidas jugadas posteriores): sirve para analizar, no simula lo que se sabía en vivo.'}
        </p>
      </Card>

      {demoActive && demo && <DemoNarrative demo={demo} cmp={cmpOk} />}

      <InboxPanel data={inbox} loading={iLoad} error={iErr} onOpen={openInbox} />

      {sLoad && <Msg kind="load">Cargando serie del jugador…</Msg>}
      {sErr && <Msg kind="err">{sErr}</Msg>}
      {!sLoad && !sErr && !series && <Msg kind="empty">Selecciona un defensivo con intervenciones observadas.</Msg>}

      {fresh && s && series && (<>
        {/* Contexto de la selección: siempre visible */}
        <div className="rounded-xl border px-4 py-3 text-sm" style={{ background: C.panel, borderColor: selPoint ? statusColor(selPoint.evaluated ? selPoint.status : 'x') : C.line }} aria-live="polite">
          <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Selección actual</div>
          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1">
            <b>{series.player.name}</b><span style={{ color: C.mute }}>{series.game.away} @ {series.game.home} · semana {series.game.week}</span>
            {selPoint && <><span>Jugada {selPoint.playId} · Q{selPoint.ctx.cuarto} {selPoint.ctx.reloj}</span><span>Índice <b>{fmt(selPoint.index, 0)}</b> · {fmt(selPoint.v, 2)} yd/s</span></>}
          </div>
          {selPoint && <div className="mt-1 text-xs" style={{ color: C.mute }}>
            Estado de <b style={{ color: C.text }}>esta jugada</b>: <span style={{ color: statusColor(selPoint.evaluated ? selPoint.status : 'x') }}>{stLabel(selPoint)}</span> · Estado <b style={{ color: C.text }}>al final del partido</b>: {s.status_label}. Pueden diferir: una secuencia baja en medio del partido no cambia el estado final si las últimas jugadas volvieron a su rango.
          </div>}
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          <Stat label="Estado al final del partido" big={<Pill status={s.status} label={s.status_label} />} foot={flagged.length ? `▲ ${flagged.length} punto(s) con marca durante el partido` : 'Sin marcas durante el partido'} color={statusColor(s.status)} />
          <Stat label="Índice mediano del partido" big={<span className="text-3xl font-bold">{fmt(s.median_index, 0)}</span>} foot="100 = su propia referencia (no es % de capacidad)" />
          <Stat label="Muestra" big={<span className="text-3xl font-bold">{s.n_comparable}<span className="text-base font-normal" style={{ color: C.mute }}> / {s.n_obs}</span></span>} foot={`comparables / observadas · ${s.n_valid} con ventana válida`} />
          <Stat label={`Referencia (${mode === 'live' ? 'creciente' : 'fija'})`} big={<span className="text-3xl font-bold">{fmt(s.v_ref, 2)}<span className="text-base font-normal" style={{ color: C.mute }}> yd/s</span></span>} foot={`n=${s.ref_n} · ${s.ref_games} partidos · ±${fmt(s.habit_pct, 0)}% · ${mode === 'live' ? 'valor al último punto' : 'toda su historia'}`} />
        </div>

        <Synthesis cmp={cmpOk} noRef={noRefOk} loading={cLoad} err={cErr} nflId={nflId!} gameId={gameId!} playId={playId} mode={mode} selPoint={selPoint} />

        <Card title="Evolución durante el partido" sub={`${series.player.name} · ${series.game.away} @ ${series.game.home} · rapidez media 0–1.0 s tras el snap relativa a su referencia (${mode === 'live' ? 'creciente, solo pasado' : 'fija'}).`}>
          <Evolution s={series} selected={playId} onPick={(p: Point) => { setRefPlayId(null); setPlayId(p.playId) }} />
        </Card>

        <div id="comparador">
          {cLoad && <Msg kind="load">Cargando replays…</Msg>}
          {cErr && <Msg kind="err">{cErr}</Msg>}
          {cmpOk && !cLoad && <CompareView cmp={cmpOk} nflId={nflId!} mode={mode} points={series.points.filter(p => p.comparable)} refPlayId={refPlayId} onRef={setRefPlayId} />}
          {noRefOk && !cLoad && <CompareView single={{ point: noRefOk.selected_only!.point, replay: noRefOk.selected_only!.replay, message: noRefOk.message }} nflId={nflId!} mode={mode} points={series.points.filter(p => p.comparable)} refPlayId={refPlayId} onRef={setRefPlayId} />}
        </div>

        <AIPanel nflId={nflId!} gameId={gameId!} mode={mode} onView={openPlay} />

        <details className="rounded-xl border p-4" style={{ background: C.panel, borderColor: C.line }}>
          <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Detalle de la revisión del partido</summary>
          <div className="mt-3"><ReviewCard s={series} /></div>
        </details>
        <details className="rounded-xl border p-4" style={{ background: C.panel, borderColor: C.line }}>
          <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Sensibilidad de la mediana del índice</summary>
          {sens ? (<div className="mt-3 text-xs">
            <p style={{ color: C.mute }}>{sens.nota}</p>
            <table className="mt-2 w-full text-left"><thead style={{ color: C.mute }}><tr><th>Variante (universo: intervenciones comparables de este partido)</th><th>Ref. típica</th><th>n</th><th className="text-right">Índice mediano</th></tr></thead><tbody>
              {sens.variantes.map(v => (
                <tr key={v.variante} className="border-t" style={{ borderColor: C.line }}>
                  <td className="py-1">{v.variante}<div style={{ color: C.mute }}>{v.descripcion}</div></td><td>{v.v_ref_tipica != null ? `${v.v_ref_tipica.toFixed(2)} yd/s` : '—'}</td><td>{v.n}</td><td className="text-right font-semibold">{fmt(v.mediana_indice, 0)}</td>
                </tr>))}
            </tbody></table>
            <p className="mt-2" style={{ color: C.mute }}>Por modo: en ese momento {fmt(sens.modos.live?.mediana_indice, 0)} (ref. final {fmt(sens.modos.live?.ref_final, 2)} yd/s, n={sens.modos.live?.ref_n}) · retrospectivo {fmt(sens.modos.retro?.mediana_indice, 0)} (ref. {fmt(sens.modos.retro?.ref_final, 2)} yd/s, n={sens.modos.retro?.ref_n}).</p>
          </div>) : <p className="mt-2 text-xs" style={{ color: C.mute }}>Cargando sensibilidad…</p>}
        </details>
        <details className="rounded-xl border p-4" style={{ background: C.panel, borderColor: C.line }}>
          <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Participación, descanso y límites</summary>
          <div className="mt-3 space-y-1 text-xs" style={{ color: C.mute }}>
            <p style={{ color: C.warn }}>Participación y descanso: no verificados.</p>
            <p>{series.participation.note}</p>
            <p>Intervalos sin observación (sombreados en la gráfica): {series.gaps.length}. No aparecer como Pass Rush en el tracking no confirma descanso.</p>
            <p>El índice mide rapidez observada, no fatiga, energía ni lesiones, y no predice el efecto de una sustitución. Umbrales heurísticos configurables. Metodología completa: METODOLOGIA.md · validación exploratoria sin etiquetas: VALIDACION.md.</p>
            {player && <p>{player.name}: {player.total_obs} intervenciones observadas en {player.total_games} partido(s) del dataset.</p>}
          </div>
        </details>
      </>)}
      {fresh && nflId != null && gameId != null && series && <ChatDrawer nflId={nflId} gameId={gameId} mode={mode} playId={playId} refPlayId={refPlayId} name={series.player.name} onView={openPlay} />}
    </Shell>
  )
}

function Synthesis({ cmp, noRef, loading, err, nflId, gameId, playId, mode, selPoint }: { cmp: Compare | null; noRef: NoRef | null; loading: boolean; err: string; nflId: number; gameId: number; playId: number | null; mode: Mode; selPoint: Point | null }) {
  const q = cmp?.quality
  const row = (t: string, v?: string) => v ? <div className="grid gap-1 sm:grid-cols-[170px_1fr]"><dt className="text-xs font-semibold uppercase tracking-wide" style={{ color: C.mute }}>{t}</dt><dd className="text-sm">{v}</dd></div> : null
  return (
    <section className="rounded-xl border p-4" style={{ background: C.panel, borderColor: C.ok }}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Hallazgo en un minuto · jugada seleccionada</h2>
        {playId != null && <a href={`api/report?nflId=${nflId}&gameId=${gameId}&playId=${playId}&mode=${mode}`} download className="rounded-md border px-3 py-1.5 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-sky-400" style={{ borderColor: C.ok, color: C.ok }}>⬇ Exportar reporte (.md)</a>}
      </div>
      {loading && <p className="text-sm" style={{ color: C.mute }}>⏳ Calculando comparación…</p>}
      {err && <p className="text-sm" style={{ color: C.warn }}>⚠ {err}</p>}
      {noRef && <p className="text-sm" style={{ color: C.warn }}>No hay una jugada de referencia comparable: {noRef.message}. {selPoint && selPoint.index != null ? `La jugada seleccionada tiene índice ${fmt(selPoint.index, 0)}, pero sin comparación contextual no se interpreta.` : ''} El replay de la jugada sigue disponible abajo.</p>}
      {cmp && !loading && (
        <dl className="space-y-2">
          {row('1 · Qué cambió', cmp.synthesis.cambio)}
          {row('2 · Magnitud y persistencia', cmp.synthesis.magnitud_persistencia)}
          {row('3 · Referencia y muestra', cmp.synthesis.referencia)}
          <div className="grid gap-1 sm:grid-cols-[170px_1fr]"><dt className="text-xs font-semibold uppercase tracking-wide" style={{ color: C.mute }}>4 · Contexto</dt>
            <dd className="text-sm">Calidad de comparación <b style={{ color: q!.nivel === 'alta' ? C.ok : C.warn }}>{q!.nivel.toUpperCase()}</b> (jugada {cmp.reference.point.playId}). {cmp.mismatches.filter(m => m.difiere).length === 0 ? 'No difieren los factores clave.' : <>Difieren: {cmp.mismatches.filter(m => m.difiere).map(m => `${m.factor} (${String(m.referencia ?? '—')} → ${String(m.seleccionada ?? '—')})`).join('; ')}.</>}</dd></div>
          <div className="grid gap-1 sm:grid-cols-[170px_1fr]"><dt className="text-xs font-semibold uppercase tracking-wide" style={{ color: C.mute }}>5 · Qué comprobar</dt>
            <dd className="text-sm"><ul className="list-disc pl-5">{cmp.synthesis.revisar.map(x => <li key={x}>{x}</li>)}</ul></dd></div>
          <p className="text-xs" style={{ color: C.mute }}>{cmp.synthesis.estado_nota} Caída de rapidez ≠ fatiga, lesión ni necesidad de sustitución.</p>
        </dl>
      )}
    </section>
  )
}

function DemoNarrative({ demo, cmp }: { demo: Demo; cmp: Compare | null }) {
  const steps: [string, string][] = [
    ['1 · Señal', demo.kind === 'normal' ? `${demo.name}: sin marcas en modo «en ese momento»; índice mediano ${fmt(demo.median_index_live, 0)} con ${demo.n_comparable} intervenciones comparables. Es variación normal.` : `${demo.name}: ${demo.flags_live} punto(s) con marca «en ese momento» y ${demo.flags_retro ?? '—'} en retrospectivo.`],
    ['2 · Evidencia', cmp ? (cmp.synthesis.magnitud_persistencia ?? cmp.synthesis.cambio) : 'Cargando…'],
    ['3 · Contexto', cmp ? cmp.synthesis.contexto : 'Cargando…'],
    ['4 · Revisión', cmp ? cmp.synthesis.revisar[0] : 'Cargando…']]
  return (
    <section className="rounded-xl border p-4" style={{ background: '#0a2236', borderColor: C.ok }} aria-label="Narrativa del caso">
      <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: C.ok }}>Caso: {demo.title}</div>
      <ol className="mt-2 grid gap-2 md:grid-cols-4">{steps.map(([t, v]) => <li key={t} className="text-xs"><b style={{ color: C.text }}>{t}</b><div style={{ color: C.mute }}>{v}</div></li>)}</ol>
      <p className="mt-2 text-[11px]" style={{ color: C.mute }}>Criterio de elección (datos reales, calculado por el backend): {demo.criterio}</p>
    </section>
  )
}

function Stat({ label, big, foot, color }: { label: string; big: React.ReactNode; foot: string; color?: string }) {
  return (
    <div className="rounded-xl border p-4" style={{ background: C.panel, borderColor: color ?? C.line }}>
      <div className="text-xs uppercase tracking-wider" style={{ color: C.mute }}>{label}</div>
      <div className="mt-2">{big}</div>
      <div className="mt-2 text-xs" style={{ color: C.mute }}>{foot}</div>
    </div>
  )
}

function ReviewCard({ s }: { s: Series }) {
  const r = s.review
  const c = statusColor(r.status)
  return (
    <section className="rounded-xl border p-4" style={{ background: C.panel, borderColor: c }}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Qué revisaría el entrenador (partido completo)</h2>
        <Pill status={r.status} label={r.status_label} />
      </div>
      <p className="text-[11px]" style={{ color: C.mute }}>{r.mode_label}</p>
      <dl className="mt-2 space-y-2 text-sm">
        <div><dt className="text-xs font-semibold" style={{ color: C.mute }}>1 · Qué cambió</dt><dd>{r.cambio}</dd></div>
        {r.referencia && <div><dt className="text-xs font-semibold" style={{ color: C.mute }}>2 · Respecto a qué</dt><dd>{r.referencia}</dd></div>}
        {r.sustento && <div><dt className="text-xs font-semibold" style={{ color: C.mute }}>3 · Qué lo sustenta</dt><dd>{r.sustento}</dd></div>}
        {r.alternativas.length > 0 && <div><dt className="text-xs font-semibold" style={{ color: C.mute }}>4 · Explicaciones alternativas</dt><dd><ul className="list-disc pl-5">{r.alternativas.map(a => <li key={a}>{a}</li>)}</ul></dd></div>}
        <div><dt className="text-xs font-semibold" style={{ color: C.mute }}>5 · Qué revisar</dt><dd><ul className="list-disc pl-5">{r.revisar.map(a => <li key={a}>{a}</li>)}</ul></dd></div>
      </dl>
      {r.rotation_note && <p className="mt-3 rounded border px-3 py-2 text-xs" style={{ borderColor: C.line, color: C.mute }}>{r.rotation_note}</p>}
    </section>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen" style={{ background: C.bg, color: C.text }}>
      <header className="border-b px-4 py-4 sm:px-6" style={{ borderColor: C.line }}>
        <h1 className="text-xl font-bold tracking-tight">Snap<span style={{ color: C.ok }}>Reverse</span> <span className="text-sm font-normal" style={{ color: C.mute }}>— Índice de Explosividad Relativa</span></h1>
        <p className="text-xs" style={{ color: C.mute }}>Convierte tracking de pass rush en una lista explicable de secuencias que vale la pena revisar, comparando a cada jugador con su historial en contextos similares. Tracking NFL 2021 (BDB).</p>
        <details className="mt-1 text-xs" style={{ color: C.mute }}>
          <summary className="cursor-pointer" style={{ color: C.text }}>¿Para quién es y qué puede (y no puede) concluirse?</summary>
          <ul className="mt-1 list-disc pl-5">
            <li><b>Para quién:</b> entrenadores de línea defensiva; analistas y comentaristas como apoyo.</li>
            <li><b>Qué facilita:</b> decidir qué jugadas ver en video primero, con la evidencia y el contexto a la vista.</li>
            <li><b>Por qué referencia individual y contexto:</b> cada jugador sale distinto según su alineación y la jugada; comparar contra su propio historial en situaciones parecidas evita confundir rol con rendimiento.</li>
            <li><b>Sí:</b> «la rapidez observada 0–1 s fue menor que su referencia en estas jugadas». <b>No:</b> fatiga, lesión, capacidad restante ni que una sustitución mejore el resultado.</li>
          </ul>
        </details>
      </header>
      <main className="mx-auto max-w-6xl space-y-4 px-4 py-5">{children}</main>
    </div>
  )
}
