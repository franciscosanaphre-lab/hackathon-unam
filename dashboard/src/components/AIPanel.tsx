import { useEffect, useRef, useState } from 'react'
import { AiReport, EvCard, Mode, post } from '../api'
import { C, Card, Msg } from './ui'

const lbl: Record<string, string> = { resumen: 'Resumen', cambio: 'Cambio', jugada: 'Jugada', comparacion: 'Comparación', alternativas: 'Alternativas' }

export function EvidenceCard({ e, onView }: { e: EvCard; onView?: (playId: number) => void }) {
  const d = e.data as Record<string, any>
  const rows = Object.entries(d).filter(([, v]) => v !== null && typeof v !== 'object').slice(0, 5)
  return (
    <div className="rounded-lg border p-3 text-xs" style={{ borderColor: C.line, background: '#081326' }}>
      <div className="flex items-center justify-between gap-2">
        <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase" style={{ background: C.line, color: C.mute }}>{e.id} · {lbl[e.type] ?? e.type}</span>
        {e.playId != null && onView && <button onClick={() => onView(e.playId!)} className="rounded border px-2 py-0.5 font-semibold" style={{ borderColor: C.ok, color: C.ok }}>Ver replay ▶</button>}
      </div>
      <div className="mt-1 font-semibold" style={{ color: C.text }}>{e.title}</div>
      <dl className="mt-1 grid grid-cols-2 gap-x-3" style={{ color: C.mute }}>
        {rows.map(([k, v]) => <div key={k} className="flex justify-between gap-2"><dt>{k.replace(/_/g, ' ')}</dt><dd style={{ color: C.text }}>{typeof v === 'number' ? (Math.round(v * 100) / 100).toString() : String(v)}</dd></div>)}
      </dl>
    </div>
  )
}

const Tag = ({ ok }: { ok: boolean }) => <span className="ml-1 rounded px-1 text-[10px]" style={{ color: ok ? C.ok : C.warn, border: `1px solid ${ok ? C.ok : C.warn}` }}>{ok ? 'cifras verificadas' : 'cifras sin verificar'}</span>

export default function AIPanel({ nflId, gameId, mode, onView }: { nflId: number; gameId: number; mode: Mode; onView: (p: number) => void }) {
  const key = `${nflId}-${gameId}-${mode}`
  const [rep, setRep] = useState<{ key: string; r: AiReport } | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const cur = useRef(key)
  cur.current = key
  useEffect(() => { setErr(''); setBusy(false) }, [key])

  const run = async (refresh = false) => {
    const k = key
    setBusy(true); setErr('')
    try {
      const r = await post<AiReport>('ai/analyze-player', { nflId, gameId, mode, refresh })
      if (cur.current === k) setRep({ key: k, r })   // descarta respuestas de otro jugador/partido/modo
    } catch (e) { if (cur.current === k) setErr((e as Error).message) }
    finally { if (cur.current === k) setBusy(false) }
  }
  const r = rep && rep.key === key ? rep.r : null
  const byId = (ids: string[]) => (r?.evidence ?? []).filter(e => ids.includes(e.id))

  return (
    <Card title="SnapReverse AI · Coach Intelligence" sub="Your Defensive Intelligence Copilot — Amazon Nova 2 Lite investiga con herramientas de Python; cada cifra se traza a evidencia."
      right={<button onClick={() => run(!!r)} disabled={busy} className="rounded-lg px-4 py-2 text-sm font-bold disabled:opacity-60" style={{ background: C.ok, color: '#04210f' }}>{busy ? 'Investigando…' : r ? 'Reanalizar' : 'ANALIZAR CON IA'}</button>}>
      {busy && <Msg kind="load">SnapReverse AI está consultando las métricas reales (≈10–20 s)…</Msg>}
      {err && !busy && <Msg kind="err">La IA no está disponible: {err}. El resto del dashboard sigue funcionando.</Msg>}
      {!r && !busy && !err && <p className="text-sm" style={{ color: C.mute }}>Pulsa «Analizar con IA» para generar un informe automático del jugador seleccionado. Nada se envía a la IA hasta que lo solicites.</p>}
      {r && !busy && (
        <div className="space-y-4 text-sm">
          {!r.structured && <p style={{ color: C.warn }}>La respuesta no tuvo el formato esperado; se muestra como texto sin verificar:<br /><span style={{ color: C.text }}>{r.raw_text}</span></p>}
          {r.structured && (<>
            <div className="rounded-lg border-l-4 px-3 py-2" style={{ borderColor: C.ok, background: '#081326' }}>
              <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Hallazgo principal {r.cached && <span>· en caché</span>}</div>
              <div className="text-base font-semibold">{r.headline}</div>
            </div>
            <div>
              <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Evidencia (datos observados)</h3>
              <ul className="space-y-1.5">{r.findings?.map((f, i) => <li key={i}>• {f.text}<Tag ok={f.verified} />{f.evidence_ids.length > 0 && <span className="ml-1 text-xs" style={{ color: C.mute }}>[{f.evidence_ids.join(', ')}]</span>}</li>)}</ul>
            </div>
            <div>
              <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Interpretación e hipótesis (no son datos)<Tag ok={!!r.interpretation_numbers_verified} /></h3>
              <p>{r.interpretation}</p>
            </div>
            <div>
              <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider" style={{ color: C.warn }}>Qué revisaría el entrenador</h3>
              <ol className="list-decimal space-y-1 pl-5">{r.recommendations?.map((x, i) => <li key={i}>{x.text}<Tag ok={x.verified} /></li>)}</ol>
            </div>
            <div>
              <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Limitaciones</h3>
              <ul className="list-disc pl-5 text-xs" style={{ color: C.mute }}>{r.limitations?.map((x, i) => <li key={i}>{x}</li>)}</ul>
            </div>
          </>)}
          <div>
            <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider" style={{ color: C.mute }}>Tarjetas de evidencia (calculadas por Python) · herramientas: {r.tools_used.join(', ')}</h3>
            <div className="grid gap-2 md:grid-cols-2">{r.evidence.map(e => <EvidenceCard key={e.id} e={e} onView={onView} />)}</div>
          </div>
        </div>
      )}
    </Card>
  )
}
