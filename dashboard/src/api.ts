// Todas las rutas son relativas (sin diagonal inicial) para funcionar bajo subrutas.
export async function api<T>(path: string): Promise<T> {
  const r = await fetch(`api/${path}`)
  if (!r.ok) {
    let msg = `Error ${r.status}`
    try { msg = (await r.json()).detail ?? msg } catch { /* sin cuerpo */ }
    const e = new Error(msg) as Error & { status?: number }
    e.status = r.status
    throw e
  }
  return r.json() as Promise<T>
}

export type Mode = 'retro' | 'live'
export interface Game { gameId: number; week: number; date: string; home: string; away: string; teams: string[]; n_interventions: number }
export interface PlayerItem { nflId: number; name: string; pos: string | null; n_obs: number; n_comparable: number; evaluable: boolean; total_obs: number; total_games: number }
export interface Ctx {
  cuarto: number; reloj: string; down: number | null; yardas_por_ganar: number | null; alineacion: string; grupo_alineacion: string
  formacion_ofensiva: string | null; cobertura: string | null; play_action: boolean | null; n_rushers: number
  bloqueadores_asignados: number; t_evento_s: number | null; resultado: string | null; personal_def: string | null
}
export interface Point {
  playId: number; order: number; elapsed: number | null; v: number | null; disp: number | null; index: number | null
  comparable: boolean; valid: boolean; excl_reason: string; status: string; v_ref: number | null; ref_n: number; ref_games: number
  ref_basis: string; habit_pct: number | null; ctx: Ctx; trend: number | null; lo: number | null; hi: number | null
}
export interface Review {
  status: string; status_label: string; mode_label?: string; rotation_note?: string; cambio: string; referencia?: string
  sustento?: string; alternativas: string[]; revisar: string[]
}
export interface Summary {
  mode: Mode; n_obs: number; n_valid: number; n_comparable: number; median_index: number | null; status: string; status_label: string
  first_flag_playId: number | null; n_flagged_points: number; v_ref: number | null; ref_n: number; ref_games: number; ref_basis: string
  habit_pct: number | null; threshold_pts: number; games_with_data: number; player_total_obs: number
}
export interface Series {
  points: Point[]; gaps: { start: number; end: number; n_plays: number; label: string }[]; summary: Summary; review: Review
  player: { nflId: number; name: string; pos: string }; game: { gameId: number; week: number; home: string; away: string; date: string }
  participation: { verified: boolean; note: string }
}
export interface Replay {
  gameId: number; playId: number; frames: number[]; snap_frame: number | null; window: [number, number] | null
  events: Record<string, string>; tracks: Record<string, (number | null)[][]>; los_x: number | null; fps: number
  players: { nflId: number; team: string | null; jersey: number | null; name: string | null; pos: string | null; role: string | null; lined_up: string | null; target: boolean }[]
  description: string; defensive_team: string; possession_team: string; sync_note: string
}
export interface Compare {
  reference: { point: Point; replay: Replay; gameId: number }; selected: { point: Point; replay: Replay; gameId: number }
  context: { campo: string; referencia: unknown; seleccionada: unknown; difiere: boolean }[]
  warnings: string[]; reference_auto: boolean; reference_rule: string
}
export interface Sensitivity { variantes: { variante: string; mediana_indice: number | null; v_ref?: number; nota?: string }[]; nota: string }
export interface Status { ready: boolean; error: string | null }
export interface Demo { nflId: number; gameId: number; team: string; name: string; week: number; n_comparable: number; has_flag_live: boolean; criterio: string }

export async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`api/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  let j: any = null
  try { j = await r.json() } catch { /* sin cuerpo */ }
  if (!r.ok) throw new Error(j?.detail ?? `Error ${r.status}`)
  return j as T
}
export interface EvCard { id: string; type: string; title: string; playId: number | null; gameId: number; data: Record<string, unknown> }
export interface AiItem { text: string; evidence_ids: string[]; verified: boolean }
export interface AiReport {
  ok: boolean; structured: boolean; headline?: string; findings?: AiItem[]; interpretation?: string; interpretation_numbers_verified?: boolean
  recommendations?: AiItem[]; limitations?: string[]; referenced_play_ids?: number[]; raw_text?: string; evidence: EvCard[]
  tools_used: string[]; nflId: number; gameId: number; mode: Mode; cached: boolean
}
export interface AiChatOut { ok: boolean; answer: string; evidence: EvCard[]; referenced_play_ids: number[]; tools_used: string[]; numbers_verified: boolean; nflId: number; gameId: number }
export interface AiCompareOut { ok: boolean; explanation: string; numbers_verified: boolean; nflId: number; gameId: number; playId: number; refPlayId: number }
