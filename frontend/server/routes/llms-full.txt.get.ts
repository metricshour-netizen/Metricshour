import { readFileSync, existsSync } from 'fs'
import { join } from 'path'

export default defineEventHandler((event) => {
  setResponseHeader(event, 'Content-Type', 'text/plain; charset=utf-8')
  setResponseHeader(event, 'Cache-Control', 'public, max-age=3600')

  // Check .output/public first (written by Celery task), fall back to source
  const candidates = [
    join(process.cwd(), '../public/llms-full.txt'),
    join(process.cwd(), 'public/llms-full.txt'),
  ]

  for (const p of candidates) {
    if (existsSync(p)) {
      return readFileSync(p, 'utf-8')
    }
  }

  setResponseStatus(event, 404)
  return 'llms-full.txt not yet generated'
})
