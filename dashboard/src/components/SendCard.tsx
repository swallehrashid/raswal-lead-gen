import { useState } from 'react'
import { useApp } from '../context'
import type { Lead } from '../data/types'
import { markSent, noWhatsapp } from '../lib/actions'
import { waPhoneLink, waWebLink } from '../lib/phone'
import { fetchFileBlob, FileImg } from './FileImg'
import { LeadHeader } from './LeadBits'
import { Button, Card, copyText, cx, useToast } from './ui'

export type Flow = 'phone' | 'desktop'

async function jpegToPng(blob: Blob): Promise<Blob> {
  const bmp = await createImageBitmap(blob)
  const c = document.createElement('canvas')
  c.width = bmp.width
  c.height = bmp.height
  c.getContext('2d')!.drawImage(bmp, 0, 0)
  return new Promise((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error('png'))), 'image/png'))
}

function Step({ n, done, children }: { n: number; done?: boolean; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className={cx('flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold', done ? 'bg-green-600 text-white' : 'bg-navy text-white')}>{done ? '✓' : n}</span>
      <div className="flex flex-1 flex-wrap gap-2">{children}</div>
    </div>
  )
}

export function SendCard({ lead, flow }: { lead: Lead; flow: Flow }) {
  const { act, api, today, settings } = useApp()
  const toast = useToast()
  const [opened, setOpened] = useState(false)
  const [shared, setShared] = useState(false)
  const [copiedImg, setCopiedImg] = useState(false)
  const [copiedCap, setCopiedCap] = useState(false)
  const phone = lead.business.phone_e164 ?? ''
  const caption = lead.message_final ?? ''
  const name = lead.business.display_name || lead.business.name

  const shareBoth = async () => {
    const blob = await fetchFileBlob(api, lead.teaser_path)
    if (!blob) return toast('No teaser image for this lead', 'err')
    const file = new File([blob], `${lead.slug ?? 'preview'}.jpg`, { type: 'image/jpeg' })
    try {
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], text: caption })
        setShared(true)
      } else toast("This browser can't share images: use Save image + Copy caption", 'err')
    } catch (e) {
      if ((e as Error).name !== 'AbortError') toast(String(e), 'err')
    }
  }
  const saveImage = async () => {
    const blob = await fetchFileBlob(api, lead.teaser_path)
    if (!blob) return toast('No teaser image', 'err')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${lead.slug ?? 'preview'}.jpg`
    a.click()
    URL.revokeObjectURL(a.href)
  }
  const copyImage = async () => {
    const blob = await fetchFileBlob(api, lead.teaser_path)
    if (!blob) return toast('No teaser image', 'err')
    try {
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': await jpegToPng(blob) })])
      setCopiedImg(true)
      toast('Image copied: paste it into the chat')
    } catch {
      toast('Copy image failed: use Save image instead', 'err')
    }
  }
  const copyCaption = async () => {
    if (await copyText(caption)) {
      setCopiedCap(true)
      toast('Caption copied')
    }
  }
  const sent = () => act(lead, markSent(lead, api.now(), today, settings.calendar, settings.pause_list), `Sent to ${name}`)
  const noWa = () => act(lead, noWhatsapp(), 'Marked No WhatsApp')

  return (
    <Card className="space-y-3 p-4">
      <LeadHeader lead={lead} showStatus={false} />
      <div className="flex gap-3">
        <FileImg path={lead.teaser_path} alt="Teaser" className="aspect-[4/5] w-28 shrink-0 rounded-xl" />
        <p className="line-clamp-[10] whitespace-pre-wrap text-sm text-navy/80">{caption}</p>
      </div>
      {flow === 'phone' ? (
        <div className="space-y-2">
          <Step n={1} done={opened}><a href={waPhoneLink(phone)} target="_blank" rel="noreferrer" onClick={() => setOpened(true)}><Button variant="wa">Open chat</Button></a></Step>
          <Step n={2} done={shared}><Button variant="primary" onClick={shareBoth}>Share image + caption</Button></Step>
          <Step n={3}><span className="text-sm text-navy/60">Pick their chat (top of recents), check the caption, send.</span></Step>
          <div className="flex gap-2 pl-10"><Button size="sm" onClick={saveImage}>Save image</Button><Button size="sm" onClick={copyCaption}>{copiedCap ? 'Caption copied ✓' : 'Copy caption'}</Button></div>
        </div>
      ) : (
        <div className="space-y-2">
          <Step n={1} done={opened}><a href={waWebLink(phone)} target="_blank" rel="noreferrer" onClick={() => setOpened(true)}><Button variant="wa">Open chat</Button></a></Step>
          <Step n={2} done={copiedImg}><Button variant="primary" onClick={copyImage}>Copy image</Button><span className="self-center text-sm text-navy/60">then paste in the chat</span></Step>
          <Step n={3} done={copiedCap}><Button onClick={copyCaption}>Copy caption</Button><span className="self-center text-sm text-navy/60">paste into the caption box, send</span></Step>
        </div>
      )}
      <div className="flex gap-2 border-t border-navy/5 pt-3">
        <Button variant="gold" className="flex-1" onClick={sent}>Sent ✓</Button>
        <Button className="flex-1" onClick={noWa}>No WhatsApp</Button>
      </div>
    </Card>
  )
}
