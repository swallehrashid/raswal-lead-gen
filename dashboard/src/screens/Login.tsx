import { useState } from 'react'
import type { Api } from '../data/api'
import { Button, Card, inputCls } from '../components/ui'

export function Login({ api, denied }: { api: Api; denied?: string }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  return (
    <div className="flex min-h-screen items-center justify-center bg-navy p-4">
      <Card className="w-full max-w-sm p-6">
        <div className="mb-1 text-2xl font-extrabold text-navy">Raswal Leads</div>
        {denied ? (
          <>
            <p className="mb-4 text-sm text-red-700">{denied} isn't allowed to use this dashboard.</p>
            <Button variant="primary" onClick={() => api.signOut()}>Sign out</Button>
          </>
        ) : (
          <form className="space-y-3" onSubmit={async (e) => {
            e.preventDefault()
            setErr(null)
            setBusy(true)
            try {
              await api.signIn(email.trim(), password)
            } catch (x) {
              setErr(String(x).replace(/^Error:\s*/, ''))
            } finally {
              setBusy(false)
            }
          }}>
            <p className="text-sm text-navy/60">Sign in to your cockpit.</p>
            <input className={inputCls} type="email" required autoComplete="email" placeholder="you@example.com"
              value={email} onChange={(e) => setEmail(e.target.value)} />
            <input className={inputCls} type="password" required autoComplete="current-password" placeholder="Password"
              value={password} onChange={(e) => setPassword(e.target.value)} />
            {err && <p className="text-sm text-red-700">{err}</p>}
            <Button variant="primary" className="w-full" type="submit" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        )}
      </Card>
    </div>
  )
}
