import { useEffect, useRef, useState } from 'react'
import { AiChatOut, EvCard, Mode, post } from '../api'
import { EvidenceCard } from './AIPanel'
import { C } from './ui'

interface Msg { role: 'user' | 'assistant'; content: string; ev?: EvCard[]; verified?: boolean; error?: boolean }
const SUGG = ['¿Qué está pasando con este jugador?', '¿Qué cambió en sus últimas intervenciones?', '¿Qué jugadas debería revisar?', '¿Hay evidencia suficiente para considerar una rotación?', '¿Qué información falta para decidir mejor?', '¿Qué táctica garantiza más sacks?']

export default function ChatDrawer({ nflId, gameId, mode, playId, refPlayId, name, onView }: { nflId: number; gameId: number; mode: Mode; playId: number | null; refPlayId: number | null; name: string; onView: (p: number) => void }) {
  const key = `${nflId}-${gameId}-${mode}`
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState<{ key: string; m: Msg[] }>({ key, m: [] })
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const cur = useRef(key); cur.current = key
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { setMsgs({ key, m: [] }); setBusy(false) }, [key])   // no mezclar conversaciones entre jugadores
  const list = msgs.key === key ? msgs.m : []
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [list.length, busy])

  const send = async (q: string) => {
    q = q.trim(); if (!q || busy) return
    const k = key
    const hist = list.filter(m => !m.error).slice(-6).map(m => ({ role: m.role, content: m.content }))
    setMsgs(s => ({ key: k, m: [...(s.key === k ? s.m : []), { role: 'user', content: q }] })); setText(''); setBusy(true)
    try {
      const r = await post<AiChatOut>('ai/chat', { nflId, gameId, mode, message: q, history: hist, playId, refPlayId })
      if (cur.current === k) setMsgs(s => ({ key: k, m: [...s.m, { role: 'assistant', content: r.answer, ev: r.evidence, verified: r.numbers_verified }] }))
    } catch (e) {
      if (cur.current === k) setMsgs(s => ({ key: k, m: [...s.m, { role: 'assistant', content: `La IA no está disponible: ${(e as Error).message}`, error: true }] }))
    } finally { if (cur.current === k) setBusy(false) }
  }

  return (<>
    <button onClick={() => setOpen(o => !o)} className="fixed bottom-5 right-5 z-30 rounded-full px-5 py-3 text-sm font-bold shadow-lg" style={{ background: C.ok, color: '#04210f' }}>{open ? 'Cerrar chat' : '💬 Preguntar a SnapReverse AI'}</button>
    {open && (
      <aside className="fixed bottom-20 right-5 z-30 flex h-[70vh] w-[min(420px,calc(100vw-2.5rem))] flex-col rounded-xl border shadow-2xl" style={{ background: C.panel, borderColor: C.line }}>
        <div className="border-b px-4 py-3" style={{ borderColor: C.line }}>
          <div className="text-sm font-bold">SnapReverse<span style={{ color: C.ok }}> AI</span></div>
          <div className="text-[11px]" style={{ color: C.mute }}>Contexto: {name} · modo {mode === 'live' ? 'en ese momento' : 'retrospectivo'}{playId ? ` · jugada ${playId}` : ''}. Consulta solo cuando preguntas.</div>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">
          {list.length === 0 && <div><p className="mb-2 text-xs" style={{ color: C.mute }}>Preguntas sugeridas:</p><div className="flex flex-wrap gap-1.5">{SUGG.map(s => <button key={s} onClick={() => send(s)} className="rounded-full border px-2.5 py-1 text-xs" style={{ borderColor: C.line, color: C.text }}>{s}</button>)}</div></div>}
          {list.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'ml-8 rounded-lg px-3 py-2' : 'rounded-lg border px-3 py-2'} style={{ background: m.role === 'user' ? C.line : '#081326', borderColor: m.error ? C.warn : C.line, color: m.error ? C.warn : C.text }}>
              <div className="whitespace-pre-wrap">{m.content.replace(/[#*]/g, '')}</div>
              {m.role === 'assistant' && !m.error && <div className="mt-1 text-[10px]" style={{ color: m.verified ? C.ok : C.warn }}>{m.verified ? 'Cifras verificadas contra las herramientas' : 'Contiene cifras no verificadas: contrástalas con las tarjetas'}</div>}
              {m.ev && m.ev.length > 0 && <div className="mt-2 space-y-2">{m.ev.map(e => <EvidenceCard key={e.id} e={e} onView={onView} />)}</div>}
            </div>
          ))}
          {busy && <div className="text-xs" style={{ color: C.mute }}>⏳ Consultando herramientas y redactando…</div>}
          <div ref={end} />
        </div>
        <form className="flex gap-2 border-t p-3" style={{ borderColor: C.line }} onSubmit={e => { e.preventDefault(); send(text) }}>
          <input value={text} maxLength={800} onChange={e => setText(e.target.value)} placeholder="Pregunta sobre este jugador…" className="flex-1 rounded-md border bg-transparent px-3 py-2 text-sm" style={{ borderColor: C.line, color: C.text }} />
          <button disabled={busy || !text.trim()} className="rounded-md px-3 text-sm font-bold disabled:opacity-50" style={{ background: C.ok, color: '#04210f' }}>Enviar</button>
        </form>
      </aside>
    )}
  </>)
}
