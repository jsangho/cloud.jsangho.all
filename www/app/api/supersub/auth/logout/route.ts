import { NextResponse } from 'next/server'
import { clearSession } from '@/supersub/server/session'

export async function POST() {
  return clearSession(NextResponse.json({ ok: true }))
}
