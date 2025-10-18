import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const tenantId = searchParams.get('tenant_id') || 'clinic-alpha';

  try {
    const statsResult = await query(
      `SELECT
        COUNT(*) as total_measurements,
        COUNT(DISTINCT device_id) as active_devices,
        AVG(pap_systolic) as avg_pap_systolic,
        MAX(pap_systolic) as max_pap_systolic,
        AVG(heart_rate) as avg_heart_rate
      FROM telemetry.heart_failure_measurements
      WHERE tenant_id = $1
        AND time > NOW() - INTERVAL '1 hour'`,
      [tenantId]
    );

    const elevatedResult = await query(
      `SELECT COUNT(*) as elevated_count
      FROM telemetry.heart_failure_measurements
      WHERE tenant_id = $1
        AND time > NOW() - INTERVAL '1 hour'
        AND pap_systolic > 28`,
      [tenantId]
    );

    const stats = statsResult.rows[0];
    return NextResponse.json({
      success: true,
      stats: {
        total_measurements: parseInt(stats.total_measurements || '0'),
        active_devices: parseInt(stats.active_devices || '0'),
        avg_pap_systolic: parseFloat(stats.avg_pap_systolic || '0'),
        max_pap_systolic: parseFloat(stats.max_pap_systolic || '0'),
        avg_heart_rate: parseFloat(stats.avg_heart_rate || '0'),
        elevated_pap_count: parseInt(elevatedResult.rows[0].elevated_count || '0'),
      },
    });
  } catch (error: any) {
    console.error('Stats API error:', error);
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 }
    );
  }
}
