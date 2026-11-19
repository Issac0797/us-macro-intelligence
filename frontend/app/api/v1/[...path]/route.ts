import { NextRequest, NextResponse } from "next/server";
export const dynamic = "force-dynamic";
async function proxy(request: NextRequest, {params}: {params: Promise<{path: string[]}>}) {
  const {path} = await params;
  const target = path.join("/");
  if (!/^(fed\/(?:overview|meetings(?:\/202[456]-\d{2}-\d{2}(?:\/documents)?)?|statements\/compare|projections|dot-plot|rates|rate-decisions|historical-snapshot|sync\/status)|analytics\/(?:metadata|correlation|rolling-correlation|lead-lag|rolling-statistics)|business-cycle\/(?:current|history)|recession-indicators|workspace\/(?:series\/search|chart-data|validate|observation-details)|workspaces(?:\/[a-f0-9-]{36})?|yield-curve(?:\/(?:spreads|changes))?|data-version|overview|health|calendar(?:\/upcoming)?|releases\/[a-f0-9]{64}(?:\/observations)?|historical-snapshot|vintage-sync\/status|vintages\/[A-Z0-9]+(?:\/observations)?|revisions(?:\/[A-Z0-9]+(?:\/summary)?)?|monitor\/status|series(?:\/[A-Z0-9]+(?:\/observations)?)?)$/.test(target))
    return NextResponse.json({detail: "Unknown API resource"}, {status: 404});
  const supplied=request.headers.get('X-Request-ID')||'';
  const id=/^[a-zA-Z0-9-]{8,64}$/.test(supplied)?supplied:crypto.randomUUID();
  const started=performance.now();
  try {
    if (request.method !== 'GET' && !/^(analytics\/(?:correlation|rolling-correlation|lead-lag|rolling-statistics)|workspace\/(?:chart-data|validate)|workspaces(?:\/[a-f0-9-]{36})?)$/.test(target))
      return NextResponse.json({detail:'Method not allowed'}, {status:405});
    const body = ['POST','PUT'].includes(request.method) ? await request.text() : undefined;
    if (body && new TextEncoder().encode(body).length > 131072)
      return NextResponse.json({detail:'Configuration exceeds 128 KiB'}, {status:413});
    const upstream = await fetch(`${process.env.BACKEND_URL || "http://127.0.0.1:8000"}/api/v1/${target}${request.nextUrl.search}`, {
      method:request.method, body, headers:{'Content-Type':'application/json','X-Request-ID':id,'X-Retry-Count':request.headers.get('X-Retry-Count')||'0'}, cache: "no-store", signal: AbortSignal.any([request.signal,AbortSignal.timeout(30000)]),
    });
    const responseHeaders:Record<string,string>={'Content-Type':'application/json','Cache-Control':'no-store','X-Request-ID':id};
    for(const key of ['retry-after','server-timing','x-cache']){const value=upstream.headers.get(key);if(value)responseHeaders[key]=value;}
    console.info(JSON.stringify({request_id:id,endpoint:'/api/v1/'+target,http_status:upstream.status,total_ms:performance.now()-started,layer:'proxy'}));
    return new NextResponse(upstream.body,{status:upstream.status,headers:responseHeaders});
  } catch(error) {
    const reason=request.signal.aborted?'client_cancelled':error instanceof Error&&error.name==='TimeoutError'?'upstream_timeout':'upstream_connection';
    const status=reason==='client_cancelled'?499:reason==='upstream_timeout'?504:502;
    console.warn(JSON.stringify({request_id:id,endpoint:'/api/v1/'+target,http_status:status,total_ms:performance.now()-started,timeout_reason:reason,layer:'proxy'}));
    return NextResponse.json({detail:'The data service is unavailable. Retry shortly.',error:{code:reason,message:'The data service is unavailable. Retry shortly.'},request_id:id},{status,headers:{'X-Request-ID':id}});
  }
}
export const GET=proxy;
export const POST=proxy;
export const PUT=proxy;
export const DELETE=proxy;
