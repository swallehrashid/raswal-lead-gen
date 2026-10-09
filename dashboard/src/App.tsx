import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { Banner } from './components/Banner'
import { cx, Spinner, ToastProvider } from './components/ui'
import { AppProvider } from './context'
import { getApi, type Api, type SessionInfo } from './data/api'
import { DemoQueue } from './screens/DemoQueue'
import { FollowUps } from './screens/FollowUps'
import { Inbox } from './screens/Inbox'
import { Login } from './screens/Login'
import { Pipeline } from './screens/Pipeline'
import { SettingsScreen } from './screens/Settings'
import { Stats } from './screens/Stats'
import { Today } from './screens/Today'

const NAV = [
  { to: '/', label: 'Today', icon: '◉' },
  { to: '/followups', label: 'Follow-ups', icon: '↻' },
  { to: '/inbox', label: 'Inbox', icon: '✉' },
  { to: '/demos', label: 'Demos', icon: '★' },
  { to: '/pipeline', label: 'Pipeline', icon: '☰' },
  { to: '/stats', label: 'Stats', icon: '▤' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
]

export default function App() {
  const [api, setApi] = useState<Api | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [session, setSession] = useState<SessionInfo | null | undefined>(undefined)
  const [admin, setAdmin] = useState<boolean | null>(null)

  useEffect(() => {
    getApi().then(setApi).catch((e) => setErr(String(e)))
  }, [])
  useEffect(() => {
    if (!api) return
    api.session().then(setSession)
    return api.onAuthChange(setSession)
  }, [api])
  useEffect(() => {
    if (api && session) api.isAdmin().then(setAdmin)
  }, [api, session])

  if (err) return <div className="p-6 text-red-700">{err}</div>
  if (!api || session === undefined) return <Spinner />
  if (!session) return <Login api={api} />
  if (admin === null) return <Spinner label="Checking access…" />
  if (!admin) return <Login api={api} denied={session.email} />

  return (
    <ToastProvider>
      <AppProvider api={api}>
        <div className="min-h-screen pb-20 sm:pb-0 sm:pl-52">
          <aside className="fixed inset-y-0 left-0 hidden w-52 flex-col bg-navy p-4 text-white sm:flex">
            <div className="mb-6 text-xl font-extrabold">Raswal <span className="text-gold">Leads</span></div>
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) =>
                cx('mb-1 rounded-xl px-3 py-2 text-sm font-semibold', isActive ? 'bg-white/10 text-gold' : 'text-white/70 hover:text-white')}>
                <span className="mr-2">{n.icon}</span>{n.label}
              </NavLink>
            ))}
            <div className="mt-auto text-xs text-white/40">{session.email}<br />{api.mode === 'mock' ? 'mock data' : 'live'}</div>
          </aside>
          <header className="sticky top-0 z-30 flex items-center justify-between bg-navy px-4 py-3 text-white sm:hidden">
            <div className="text-lg font-extrabold">Raswal <span className="text-gold">Leads</span></div>
            <NavLink to="/settings" className="text-white/70">⚙</NavLink>
          </header>
          <main className="mx-auto max-w-4xl space-y-4 p-3 sm:p-6">
            <Banner />
            <Routes>
              <Route path="/" element={<Today />} />
              <Route path="/followups" element={<FollowUps />} />
              <Route path="/inbox" element={<Inbox />} />
              <Route path="/demos" element={<DemoQueue />} />
              <Route path="/pipeline" element={<Pipeline />} />
              <Route path="/stats" element={<Stats />} />
              <Route path="/settings" element={<SettingsScreen />} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </main>
          <nav className="safe-bottom fixed inset-x-0 bottom-0 z-30 grid grid-cols-6 border-t border-navy/10 bg-white sm:hidden">
            {NAV.slice(0, 6).map((n) => (
              <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) =>
                cx('flex flex-col items-center py-2 text-[11px] font-semibold', isActive ? 'text-navy' : 'text-navy/40')}>
                <span className="text-lg leading-none">{n.icon}</span>{n.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </AppProvider>
    </ToastProvider>
  )
}
