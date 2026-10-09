import { createContext, useCallback, useContext, useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'

export function cx(...c: Array<string | false | null | undefined>) {
  return c.filter(Boolean).join(' ')
}

type Variant = 'primary' | 'gold' | 'ghost' | 'danger' | 'outline' | 'wa'
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-navy text-white hover:bg-navy-700',
  gold: 'bg-gold text-navy hover:brightness-95',
  ghost: 'bg-transparent text-navy hover:bg-navy/5',
  danger: 'bg-red-600 text-white hover:bg-red-700',
  outline: 'border border-navy/20 bg-white text-navy hover:bg-navy/5',
  wa: 'bg-[#25D366] text-[#073b1d] hover:brightness-95',
}

export function Button({ variant = 'outline', className, size = 'md', ...p }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' }) {
  return (
    <button
      {...p}
      className={cx('inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition disabled:opacity-40',
        size === 'sm' ? 'px-3 py-1.5 text-sm' : 'px-4 py-2.5 text-[15px]', VARIANTS[variant], className)}
    />
  )
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('rounded-2xl bg-white shadow-sm ring-1 ring-navy/5', className)}>{children}</div>
}

export function Badge({ children, tone = 'grey', className }: { children: ReactNode; tone?: string; className?: string }) {
  const tones: Record<string, string> = {
    grey: 'bg-navy/5 text-navy/70', navy: 'bg-navy text-white', gold: 'bg-gold-100 text-[#7a5605]',
    cyan: 'bg-cyan-100 text-[#155675]', green: 'bg-green-100 text-green-800', red: 'bg-red-100 text-red-700',
    amber: 'bg-amber-100 text-amber-800',
  }
  return <span className={cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold', tones[tone] ?? tones.grey, className)}>{children}</span>
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return <div className="flex items-center gap-2 p-6 text-sm text-navy/60"><span className="h-4 w-4 animate-spin rounded-full border-2 border-navy/20 border-t-navy" />{label}</div>
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-navy/15 bg-white/60 p-8 text-center">
      <p className="font-semibold text-navy">{title}</p>
      {children && <div className="mt-1 text-sm text-navy/60">{children}</div>}
    </div>
  )
}

export function Tabs<T extends string>({ value, onChange, items }:
  { value: T; onChange: (v: T) => void; items: Array<{ value: T; label: ReactNode }> }) {
  return (
    <div className="flex gap-1 rounded-xl bg-navy/5 p-1">
      {items.map((i) => (
        <button key={i.value} onClick={() => onChange(i.value)}
          className={cx('flex-1 rounded-lg px-3 py-1.5 text-sm font-semibold transition',
            value === i.value ? 'bg-white text-navy shadow-sm' : 'text-navy/60 hover:text-navy')}>
          {i.label}
        </button>
      ))}
    </div>
  )
}

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  useEffect(() => {
    if (!open) return
    const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-navy/40 sm:items-center" onClick={onClose}>
      <div className="safe-bottom max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-paper p-4 sm:max-w-2xl sm:rounded-3xl"
        onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="text-lg font-bold text-navy">{title}</div>
          <button onClick={onClose} className="rounded-full px-2 text-2xl leading-none text-navy/50 hover:text-navy" aria-label="Close">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- toasts
const ToastCtx = createContext<(msg: string, tone?: 'ok' | 'err') => void>(() => undefined)
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Array<{ id: number; msg: string; tone: 'ok' | 'err' }>>([])
  const push = useCallback((msg: string, tone: 'ok' | 'err' = 'ok') => {
    const id = Date.now() + Math.random()
    setItems((x) => [...x, { id, msg, tone }])
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), tone === 'err' ? 6000 : 2500)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 sm:bottom-6">
        {items.map((t) => (
          <div key={t.id} className={cx('rounded-xl px-4 py-2 text-sm font-semibold shadow-lg', t.tone === 'err' ? 'bg-red-600 text-white' : 'bg-navy text-white')}>{t.msg}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    ta.remove()
    return ok
  }
}

export function CopyButton({ text, label = 'Copy', variant = 'outline', size = 'md', className }:
  { text: string; label?: string; variant?: Variant; size?: 'sm' | 'md'; className?: string }) {
  const toast = useToast()
  return <Button variant={variant} size={size} className={className}
    onClick={async () => toast((await copyText(text)) ? 'Copied' : 'Copy failed', 'ok')}>{label}</Button>
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-navy/50">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-navy/50">{hint}</span>}
    </label>
  )
}

export const inputCls = 'w-full rounded-xl border border-navy/15 bg-white px-3 py-2 text-[15px] outline-none focus:border-cyan focus:ring-2 focus:ring-cyan/20'
