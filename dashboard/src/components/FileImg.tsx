import { useEffect, useState } from 'react'
import { useApp } from '../context'
import { cx } from './ui'

/** Image from private storage (signed URL), with a placeholder. */
export function FileImg({ path, alt, className, placeholder = 'No image' }:
  { path: string | null | undefined; alt: string; className?: string; placeholder?: string }) {
  const { api } = useApp()
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let alive = true
    setFailed(false)
    api.fileUrl(path).then((u) => alive && setUrl(u))
    return () => {
      alive = false
    }
  }, [api, path])
  if (!path || failed || !url)
    return <div className={cx('flex items-center justify-center bg-navy/5 text-xs text-navy/40', className)}>{path && !failed && !url ? '…' : placeholder}</div>
  return <img src={url} alt={alt} className={cx('object-cover', className)} loading="lazy" onError={() => setFailed(true)} />
}

export async function fetchFileBlob(api: { fileUrl: (p: string) => Promise<string | null> }, path: string | null): Promise<Blob | null> {
  if (!path) return null
  const url = await api.fileUrl(path)
  if (!url) return null
  const r = await fetch(url)
  return r.ok ? r.blob() : null
}
