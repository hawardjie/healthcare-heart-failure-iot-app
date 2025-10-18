import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const tenantId = searchParams.get('tenant_id') || 'clinic-alpha';

  try {
    const result = await query(
      `SELECT
        d.device_id,
        d.tenant_id,
        d.device_type,
        d.last_seen_at,
        COUNT(t.time) as reading_count_24h,
        AVG(t.pap_systolic) as avg_pap_systolic,
        MAX(t.pap_systolic) as max_pap_systolic
      FROM public.devices d
      LEFT JOIN telemetry.heart_failure_measurements t
        ON d.device_id = t.device_id
        AND t.time > NOW() - INTERVAL '24 hours'
      WHERE d.tenant_id = $1
      GROUP BY d.device_id, d.tenant_id, d.device_type, d.last_seen_at
      ORDER BY d.last_seen_at DESC NULLS LAST
      LIMIT 50`,
      [tenantId]
    );

    return NextResponse.json({
      success: true,
      count: result.rows.length,
      devices: result.rows,
    });
  } catch (error: any) {
    console.error('Devices API error:', error);
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 }
    );
  }
}
