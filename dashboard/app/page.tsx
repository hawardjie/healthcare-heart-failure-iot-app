'use client';

import { useState, useEffect } from 'react';

interface Stats {
  total_measurements: number;
  active_devices: number;
  avg_pap_systolic: number;
  max_pap_systolic: number;
  avg_heart_rate: number;
  elevated_pap_count: number;
}

interface Telemetry {
  time: string;
  device_id: string;
  pap_systolic: number;
  pap_diastolic: number;
  heart_rate: number;
  signal_quality: number;
}

export default function Dashboard() {
  const [tenant, setTenant] = useState('clinic-alpha');
  const [stats, setStats] = useState<Stats | null>(null);
  const [telemetry, setTelemetry] = useState<Telemetry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [statsRes, telemetryRes] = await Promise.all([
        fetch(`/api/stats?tenant_id=${tenant}`),
        fetch(`/api/telemetry?tenant_id=${tenant}&limit=20`),
      ]);

      const statsData = await statsRes.json();
      const telemetryData = await telemetryRes.json();

      if (statsData.success) setStats(statsData.stats);
      if (telemetryData.success) setTelemetry(telemetryData.data);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [tenant]);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Heart Failure IoT Dashboard
          </h1>
          <p className="text-gray-600">Real-time CardioMEMS device monitoring</p>
        </div>

        {/* Tenant Selector */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Tenant
          </label>
          <select
            value={tenant}
            onChange={(e) => setTenant(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          >
            <option value="clinic-alpha">Alpha Cardiology Clinic</option>
            <option value="hospital-beta">Beta Regional Hospital</option>
          </select>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
            <p className="mt-4 text-gray-600">Loading dashboard...</p>
          </div>
        ) : (
          <>
            {/* Stats Grid */}
            {stats && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <StatCard
                  title="Total Readings (1h)"
                  value={stats.total_measurements.toLocaleString()}
                  icon="📊"
                />
                <StatCard
                  title="Active Devices"
                  value={stats.active_devices.toString()}
                  icon="📱"
                />
                <StatCard
                  title="Avg PAP Systolic"
                  value={`${stats.avg_pap_systolic.toFixed(1)} mmHg`}
                  icon="💓"
                  warning={stats.avg_pap_systolic > 28}
                />
                <StatCard
                  title="Elevated PAP Alerts"
                  value={stats.elevated_pap_count.toString()}
                  icon="🚨"
                  warning={stats.elevated_pap_count > 0}
                />
              </div>
            )}

            {/* Recent Telemetry Table */}
            <div className="bg-white rounded-lg shadow-md overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
                <h2 className="text-xl font-semibold text-gray-800">
                  Recent Telemetry ({telemetry.length} readings)
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Time
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Device ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        PAP (Sys/Dia)
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Heart Rate
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Signal Quality
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {telemetry.map((reading, idx) => {
                      const isElevated = reading.pap_systolic > 28;
                      return (
                        <tr key={idx} className={isElevated ? 'bg-red-50' : ''}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {new Date(reading.time).toLocaleTimeString()}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            {reading.device_id}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            <span className={isElevated ? 'font-bold text-red-600' : ''}>
                              {reading.pap_systolic.toFixed(1)}
                            </span>
                            {' / '}
                            {reading.pap_diastolic.toFixed(1)} mmHg
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {reading.heart_rate} bpm
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {(reading.signal_quality * 100).toFixed(0)}%
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            {isElevated ? (
                              <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                                ELEVATED
                              </span>
                            ) : (
                              <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                                NORMAL
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
  warning = false,
}: {
  title: string;
  value: string;
  icon: string;
  warning?: boolean;
}) {
  return (
    <div
      className={`bg-white rounded-lg shadow-md p-6 ${
        warning ? 'border-2 border-red-400' : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
          <p className={`text-2xl font-bold ${warning ? 'text-red-600' : 'text-gray-900'}`}>
            {value}
          </p>
        </div>
        <div className="text-4xl">{icon}</div>
      </div>
    </div>
  );
}
