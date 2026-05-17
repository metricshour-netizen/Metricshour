import { readFileSync, existsSync } from 'fs'
import { join } from 'path'

export default defineEventHandler((event) => {
  setResponseHeader(event, 'Content-Type', 'text/plain; charset=utf-8')
  setResponseHeader(event, 'Cache-Control', 'public, max-age=3600')

  const candidates = [
    join(process.cwd(), '../public/llms.txt'),
    join(process.cwd(), 'public/llms.txt'),
  ]

  for (const p of candidates) {
    if (existsSync(p)) {
      return readFileSync(p, 'utf-8')
    }
  }

  return '# MetricsHour\n\n> Index not yet generated. Check back shortly.'
})
