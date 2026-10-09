import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import type { Api } from './data/api'
import type { Lead, Settings } from './data/types'
import type { Action } from './lib/actions'
import { useToast } from './components/ui'

interface AppState {
  api: Api
  settings: Settings
  today: string
  reloadSettings: () => Promise<void>
  /** Apply an action and report it; returns the promoted reserve id, if any. */
  act: (lead: Lead, action: Action, done?: string) => Promise<string | null>
  version: number
}

const Ctx = createContext<AppState | null>(null)

export function useApp(): AppState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useApp outside provider')
  return v
}

export function AppProvider({ api, children }: { api: Api; children: ReactNode }) {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const toast = useToast()
  const reloadSettings = useCallback(async () => {
    try {
      setSettings(await api.settings())
    } catch (e) {
      setError(String(e))
    }
  }, [api])
  useEffect(() => {
    void reloadSettings()
  }, [reloadSettings])
  const act = useCallback(async (lead: Lead, action: Action, done?: string) => {
    try {
      const { promoted } = await api.apply(lead, action)
      setVersion((v) => v + 1)
      if (done) toast(promoted ? `${done} · a reserve was promoted` : done)
      return promoted
    } catch (e) {
      toast(`Failed: ${String(e)}`, 'err')
      throw e
    }
  }, [api, toast])
  if (error) return <div className="p-6 text-red-700">Could not load settings: {error}</div>
  if (!settings) return <div className="p-6 text-navy/60">Loading…</div>
  return <Ctx.Provider value={{ api, settings, today: api.today(), reloadSettings, act, version }}>{children}</Ctx.Provider>
}

/** Load async data and reload when deps or the global version change. */
export function useData<T>(load: () => Promise<T>, deps: unknown[]): { data: T | null; error: string | null; reload: () => void } {
  const { version } = useApp()
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let alive = true
    load().then((d) => alive && (setData(d), setError(null))).catch((e) => alive && setError(String(e)))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version, tick])
  return { data, error, reload: () => setTick((t) => t + 1) }
}
