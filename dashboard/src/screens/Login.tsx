import { useState } from 'react'
import type { Api } from '../data/api'
import { Button, Card, inputCls } from '../components/ui'

export function Login({ api, denied }: { api: Api; denied?: string }) {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
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
        ) : sent ? (
          <p className="text-sm text-navy/70">Check <b>{email}</b> for the sign-in link. You can close this tab.</p>
        ) : (
          <form className="space-y-3" onSubmit={async (e) => {
            e.preventDefault()
            setErr(null)
            try {
              await api.signIn(email.trim())
              setSent(true)
            } catch (x) {
              setErr(String(x))
            }
          }}>
            <p className="text-sm text-navy/60">Sign in with a magic link.</p>
            <input className={inputCls} type="email" required autoComplete="email" placeholder="you@example.com"
              value={email} onChange={(e) => setEmail(e.target.value)} />
            {err && <p className="text-sm text-red-700">{err}</p>}
            <Button variant="primary" className="w-full" type="submit">Send link</Button>
          </form>
        )}
      </Card>
    </div>
  )
}
