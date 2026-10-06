import { NextResponse } from 'next/server'
import { getBackend } from '@/supersub/server/backend'
import { toErrorResponse } from '@/supersub/server/handler'

export async function GET(_req: Request, ctx: { params: Promise<{ slug: string }> }) {
  const { slug } = await ctx.params
  try {
    return NextResponse.json(await getBackend().getPublicCard(slug))
  } catch (e) {
    return toErrorResponse(e)
  }
}
