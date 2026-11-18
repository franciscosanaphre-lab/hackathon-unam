import { useEffect, useMemo, useState } from 'react'
import { api, Compare, Demo, Game, Mode, PlayerItem, Point, Sensitivity, Series, Status } from './api'
import AIPanel from './components/AIPanel'
import ChatDrawer from './components/ChatDrawer'
import CompareView from './components/Compare'
import Evolution from './components/Evolution'
import { C, Card, fmt, Msg, Pill, statusColor } from './components/ui'

const sel = 'rounded-md border bg-transparent px-2 py-1.5 text-sm'

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
  const [cLoad, setCLoad] = useState(false)
  const [cErr, setCErr] = useState('')
  const [refPlayId, setRefPlayId] = useState<number | null>(null)
  const [sens, setSens] = useState<Sensitivity | null>(null)
  const [demo, setDemo] = useState<Demo | null>(null)
  const [pending, setPending] = useState<{ nflId: number; playId?: number } | null>(null)

  // Espera a que el backend termine de calcular al arrancar
  useEffect(() => {
    let stop = false
    const poll = async () => {
      try {
        const s = await api<Status>('status')
        if (s.error) { setErr(s.error); setReady('err'); return }
        if (!s.ready) { if (!stop) setTimeout(poll, 1500); return }
        const [g, d] = await Promise.all([api<Game[]>('games'), api<Demo>('demo-case').catch(() => null)])
        if (stop) return
        setGames(g); setDemo(d); setReady('ok')
        if (d) { setGameId(d.gameId); setTeam(d.team); setPending({ nflId: d.nflId }) }
        else if (g.length) { setGameId(g[0].gameId); setTeam(g[0].teams[0]) }
      } catch (e) { if (!stop) { setErr((e as Error).message); setReady('err') } }
    }
    poll()
    return () => { stop = true }
  }, [])

  const game = games.find(g => g.gameId === gameId)
  useEffect(() => {
    if (gameId == null || !team) return
    setPlayers(null)
    api<PlayerItem[]>(`games/${gameId}/teams/${team}/players`).then(p => {
      setPlayers(p)
      setNflId(n => (pending ? pending.nflId : n != null && p.some(x => x.nflId === n) ? n : (p.find(x => x.evaluable) ?? p[0])?.nflId ?? null))
    }).catch(() => { setPlayers([]); setNflId(null) })
  }, [gameId, team]) // eslint-disable-line

  useEffect(() => {
    if (nflId == null || gameId == null) { setSeries(null); return }
    setSLoad(true); setSErr(''); setCmp(null); setSens(null); setRefPlayId(null)
    api<Series>(`players/${nflId}/games/${gameId}/series?mode=${mode}`).then(s => {
      setSeries(s)
      const first = s.summary.first_flag_playId
      const pick = pending?.playId ?? first ?? s.points[s.points.length - 1]?.playId ?? null
      setPlayId(pick); setPending(null)
    }).catch(e => { setSeries(null); setSErr((e as Error).message) }).finally(() => setSLoad(false))
    api<Sensitivity>(`players/${nflId}/games/${gameId}/sensitivity`).then(setSens).catch(() => setSens(null))
  }, [nflId, gameId, mode]) // eslint-disable-line

  useEffect(() => {
    if (nflId == null || gameId == null || playId == null) return
    setCLoad(true); setCErr('')
    api<Compare>(`compare?nflId=${nflId}&gameId=${gameId}&playId=${playId}&mode=${mode}${refPlayId ? `&refGameId=${gameId}&refPlayId=${refPlayId}` : ''}`).then(setCmp).catch(e => { setCmp(null); setCErr((e as Error).message) }).finally(() => setCLoad(false))
  }, [nflId, gameId, playId, mode, refPlayId])

  const s = series?.summary
  const player = players?.find(p => p.nflId === nflId)
  const flagged = useMemo(() => series?.points.filter(p => p.status === 'caida_para_revisar') ?? [], [series])

  if (ready === 'load') return <Shell><Msg kind="load">El servidor está calculando las métricas sobre los datos de tracking (≈10 s)…</Msg></Shell>
  if (ready === 'err') return <Shell><Msg kind="err">No se pudieron cargar los datos: {err}</Msg></Shell>

  return (
    <Shell>
      <Card title="Selección" right={
        <div className="flex gap-1 rounded-lg border p-0.5 text-xs" style={{ borderColor: C.line }}>
          {(['live', 'retro'] as Mode[]).map(m => (
            <button key={m} onClick={() => setMode(m)} className="rounded-md px-3 py-1.5 font-semibold" style={{ background: mode === m ? C.line : 'transparent', color: mode === m ? C.text : C.mute }}>
              {m === 'live' ? 'En ese momento' : 'Retrospectivo'}
            </button>))}
        </div>}>
        <div className="flex flex-wrap items-end gap-3 text-xs" style={{ color: C.mute }}>
          <label>Partido<br />
            <select className={sel} style={{ borderColor: C.line, color: C.text }} value={gameId ?? ''} onChange={e => { const g = games.find(x => x.gameId === Number(e.target.value))!; setPending(null); setGameId(g.gameId); setTeam(g.teams[0]) }}>
              {games.map(g => <option key={g.gameId} value={g.gameId} style={{ background: C.bg }}>S{g.week} · {g.away} @ {g.home} ({g.date})</option>)}
            </select></label>
          <label>Equipo (defensa)<br />
            <select className={sel} style={{ borderColor: C.line, color: C.text }} value={team} onChange={e => { setPending(null); setTeam(e.target.value) }}>
              {(game?.teams ?? []).map(t => <option key={t} style={{ background: C.bg }}>{t}</option>)}
            </select></label>
          <label>Defensivo (rol Pass Rush)<br />
            <select className={sel} style={{ borderColor: C.line, color: C.text, minWidth: 260 }} value={nflId ?? ''} onChange={e => { setPending(null); setNflId(Number(e.target.value)) }}>
              {(players ?? []).map(p => <option key={p.nflId} value={p.nflId} style={{ background: C.bg }}>{p.name} ({p.pos}) · {p.n_obs} obs{p.evaluable ? '' : ' · pocas'}</option>)}
            </select></label>
          {demo && <button className="rounded-md border px-3 py-1.5 text-xs font-semibold" style={{ borderColor: C.ok, color: C.ok }} onClick={() => { setGameId(demo.gameId); setTeam(demo.team); setPending({ nflId: demo.nflId }); setNflId(demo.nflId) }}>Cargar caso demo</button>}
        </div>
        <p className="mt-2 text-xs" style={{ color: C.mute }}>
          {mode === 'live' ? 'Modo «en ese momento»: referencia y umbrales usan solo intervenciones anteriores a cada punto.' : 'Modo «retrospectivo»: referencia con toda la evidencia disponible del jugador (incluye jugadas posteriores).'}
        </p>
      </Card>

      {sLoad && <Msg kind="load">Cargando serie del jugador…</Msg>}
      {sErr && <Msg kind="err">{sErr}</Msg>}
      {!sLoad && !sErr && !series && <Msg kind="empty">Selecciona un defensivo con intervenciones observadas.</Msg>}

      {series && s && !sLoad && (<>
        <div className="grid gap-4 md:grid-cols-4">
          <Stat label="Estado (último punto)" big={<Pill status={s.status} label={s.status_label} />} foot={flagged.length ? `${flagged.length} punto(s) con marca durante el partido` : 'Sin marcas durante el partido'} color={statusColor(s.status)} />
          <Stat label="Índice mediano del partido" big={<span className="text-3xl font-bold">{fmt(s.median_index, 0)}</span>} foot="100 = su propia referencia (no es % de capacidad)" />
          <Stat label="Muestra" big={<span className="text-3xl font-bold">{s.n_comparable}<span className="text-base font-normal" style={{ color: C.mute }}> / {s.n_obs}</span></span>} foot={`intervenciones comparables / observadas · ${s.n_valid} con ventana válida`} />
          <Stat label="Referencia propia" big={<span className="text-3xl font-bold">{fmt(s.v_ref, 2)}<span className="text-base font-normal" style={{ color: C.mute }}> yd/s</span></span>} foot={`n=${s.ref_n} · ${s.ref_games} partidos · variación ±${fmt(s.habit_pct, 0)}%`} />
        </div>

        <AIPanel nflId={nflId!} gameId={gameId!} mode={mode} onView={(p) => { setRefPlayId(null); setPlayId(p); document.getElementById('comparador')?.scrollIntoView({ behavior: 'smooth' }) }} />

        <Card title="Evolución durante el partido" sub={`${series.player.name} · ${series.game.away} @ ${series.game.home} · rapidez media 0–1.0 s tras el snap relativa a su referencia. Clic en un punto para abrir la jugada.`}>
          <Evolution s={series} selected={playId} onPick={(p: Point) => setPlayId(p.playId)} />
        </Card>

        <div className="grid gap-4 lg:grid-cols-3">
          <Card title="Participación y descanso">
            <p className="text-sm" style={{ color: C.warn }}>No verificados.</p>
            <p className="mt-1 text-xs" style={{ color: C.mute }}>{series.participation.note}</p>
            <p className="mt-2 text-xs" style={{ color: C.mute }}>Intervalos sin observación (sombreados en la gráfica): {series.gaps.length}. Que no aparezca en el tracking como Pass Rush no confirma descanso.</p>
          </Card>
          <div className="lg:col-span-2">
            <ReviewCard s={series} />
          </div>
        </div>

        {cLoad && <Msg kind="load">Cargando replays…</Msg>}
        {cErr && <Msg kind="err">{cErr}</Msg>}
        {cmp && !cLoad && <div id="comparador"><CompareView cmp={cmp} nflId={nflId!} mode={mode} points={series.points.filter(p => p.comparable)} refPlayId={refPlayId} onRef={setRefPlayId} /></div>}

        {sens && (
          <Card title="Sensibilidad de la mediana del índice" sub={sens.nota}>
            <table className="w-full text-left text-xs"><tbody>
              {sens.variantes.map(v => (
                <tr key={v.variante} className="border-t" style={{ borderColor: C.line }}>
                  <td className="py-1">{v.variante}</td><td style={{ color: C.mute }}>{v.v_ref != null ? `ref ${v.v_ref.toFixed(2)}` : v.nota}</td>
                  <td className="text-right font-semibold">{fmt(v.mediana_indice, 0)}</td>
                </tr>))}
            </tbody></table>
          </Card>
        )}
        {player && <p className="text-xs" style={{ color: C.mute }}>{player.name}: {player.total_obs} intervenciones observadas en {player.total_games} partido(s) del dataset.</p>}
      </>)}
      {series && nflId != null && gameId != null && <ChatDrawer nflId={nflId} gameId={gameId} mode={mode} playId={playId} refPlayId={refPlayId} name={series.player.name} onView={(p) => { setRefPlayId(null); setPlayId(p); document.getElementById('comparador')?.scrollIntoView({ behavior: 'smooth' }) }} />}
    </Shell>
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
        <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Qué revisaría el entrenador</h2>
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
      {r.rotation_note && <p className="mt-3 rounded border px-3 py-2 text-xs" style={{ borderColor: C.line, color: C.mute }}>{r.rotation_note} Esto no mide fatiga, energía ni lesión, ni predice si una sustitución mejoraría el resultado.</p>}
    </section>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen" style={{ background: C.bg, color: C.text }}>
      <header className="border-b px-6 py-4" style={{ borderColor: C.line }}>
        <h1 className="text-xl font-bold tracking-tight">Snap<span style={{ color: C.ok }}>Reverse</span> <span className="text-sm font-normal" style={{ color: C.mute }}>— Índice de Explosividad Relativa</span></h1>
        <p className="text-xs" style={{ color: C.mute }}>¿Cuándo muestra un defensivo una caída de explosividad respecto a su propia referencia que merece revisar? Tracking NFL 2021 (BDB) · solo explosividad observada, no fatiga.</p>
      </header>
      <main className="mx-auto max-w-6xl space-y-4 px-4 py-5">{children}</main>
    </div>
  )
}
