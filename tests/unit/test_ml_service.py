"""
Unit tests for ML anomaly detection service
"""

import pytest
from ml_service.service import SimpleAnomalyDetector, TelemetryInput, BaselineStats


def test_normal_reading():
    """Test that normal PAP values don't trigger anomalies"""
    telemetry = TelemetryInput(
        timestamp="2025-10-17T12:00:00Z",
        deviceId="TEST-001",
        tenantId="test-tenant",
        pap_systolic=22.0,
        pap_diastolic=9.0,
        pap_mean=13.3,
        heart_rate=75,
        signal_quality=0.95
    )

    result = SimpleAnomalyDetector.score(telemetry)

    assert result.is_anomaly is False
    assert result.anomaly_score < 0.5
    assert "Normal reading" in result.reason


def test_elevated_pap_triggers_anomaly():
    """Test that elevated PAP triggers anomaly detection"""
    telemetry = TelemetryInput(
        timestamp="2025-10-17T12:00:00Z",
        deviceId="TEST-001",
        tenantId="test-tenant",
        pap_systolic=36.0,  # Critical level
        pap_diastolic=17.0,
        pap_mean=23.3,
        heart_rate=85,
        signal_quality=0.90
    )

    result = SimpleAnomalyDetector.score(telemetry)

    assert result.is_anomaly is True
    assert result.anomaly_score >= 0.5
    assert "CRITICAL" in result.reason or "Elevated" in result.reason


def test_statistical_outlier_detection():
    """Test that statistical deviation from baseline is detected"""
    telemetry = TelemetryInput(
        timestamp="2025-10-17T12:00:00Z",
        deviceId="TEST-001",
        tenantId="test-tenant",
        pap_systolic=35.0,
        pap_diastolic=15.0,
        pap_mean=21.7,
        heart_rate=75,
        signal_quality=0.95
    )

    baseline = BaselineStats(
        avg_pap_systolic=22.0,
        stddev_pap_systolic=2.0,
        avg_pap_diastolic=9.0,
        stddev_pap_diastolic=1.5,
        avg_heart_rate=75.0
    )

    result = SimpleAnomalyDetector.score(telemetry, baseline)

    assert result.is_anomaly is True
    # Z-score = (35 - 22) / 2 = 6.5, which is > 2.5 threshold


def test_tachycardia_detection():
    """Test that tachycardia contributes to anomaly score"""
    telemetry = TelemetryInput(
        timestamp="2025-10-17T12:00:00Z",
        deviceId="TEST-001",
        tenantId="test-tenant",
        pap_systolic=24.0,
        pap_diastolic=10.0,
        pap_mean=14.7,
        heart_rate=115,  # Tachycardia
        signal_quality=0.95
    )

    result = SimpleAnomalyDetector.score(telemetry)

    assert "Tachycardia" in result.reason
    assert result.features['heart_rate'] == 115


def test_poor_signal_quality():
    """Test that poor signal quality is flagged"""
    telemetry = TelemetryInput(
        timestamp="2025-10-17T12:00:00Z",
        deviceId="TEST-001",
        tenantId="test-tenant",
        pap_systolic=24.0,
        pap_diastolic=10.0,
        pap_mean=14.7,
        heart_rate=75,
        signal_quality=0.65  # Poor quality
    )

    result = SimpleAnomalyDetector.score(telemetry)

    assert "signal quality" in result.reason.lower()
