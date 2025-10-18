import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const tenantId = searchParams.get('tenant_id') || 'clinic-alpha';
  const limit = parseInt(searchParams.get('limit') || '100');

  try {
    const result = await query(
      `SELECT
        time, device_id, tenant_id,
        pap_systolic, pap_diastolic, pap_mean,
        heart_rate, signal_quality,
        battery_level
      FROM telemetry.heart_failure_measurements
      WHERE tenant_id = $1
      ORDER BY time DESC
      LIMIT $2`,
      [tenantId, limit]
    );

    // Convert numeric strings to numbers
    const data = result.rows.map(row => ({
      ...row,
      pap_systolic: parseFloat(row.pap_systolic),
      pap_diastolic: parseFloat(row.pap_diastolic),
      pap_mean: parseFloat(row.pap_mean),
      heart_rate: parseInt(row.heart_rate),
      signal_quality: parseFloat(row.signal_quality),
      battery_level: parseInt(row.battery_level),
    }));

    return NextResponse.json({
      success: true,
      count: data.length,
      data: data,
    });
  } catch (error: any) {
    console.error('Telemetry API error:', error);
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 }
    );
  }
}
