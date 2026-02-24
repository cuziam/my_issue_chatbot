export function formatDate(dateStr: string): string {
  const ts = Number(dateStr)
  if (!isNaN(ts) && ts > 1e12) {
    return new Date(ts).toLocaleString('ko-KR')
  }
  return new Date(dateStr).toLocaleString('ko-KR')
}

export function formatDuration(ms?: number): string {
  if (!ms) return ''
  const s = Math.round(ms / 1000)
  if (s >= 60) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${s}s`
}

export function formatDurationSec(seconds: number | null): string {
  if (seconds === null) return '-'
  if (seconds >= 60) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  return `${seconds}s`
}

export function formatTime(ts?: string): string {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
