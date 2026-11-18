import { MessageCircle } from 'lucide-react'

export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-[30%] bg-gradient-to-br from-accent to-accent-2 shadow-[0_6px_20px_-6px_var(--accent)]"
      style={{ width: size, height: size }}
    >
      <MessageCircle className="text-white" style={{ width: size * 0.55, height: size * 0.55 }} strokeWidth={2.4} />
    </div>
  )
}

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark />
      <span className="font-display text-lg font-bold tracking-tight">Askive</span>
    </div>
  )
}
