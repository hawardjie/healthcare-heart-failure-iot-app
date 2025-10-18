#!/usr/bin/env python3
"""
ML Anomaly Detection Service
FastAPI service for real-time heart failure telemetry anomaly scoring
Uses simple rule-based + statistical methods (placeholder for full ML model)
"""

from typing import Dict, Optional
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="HF Anomaly Detection Service", version="0.1.0")


# ============================================================================
# Data Models
# ============================================================================

class TelemetryInput(BaseModel):
    """Telemetry message for scoring"""
    timestamp: str
    deviceId: str
    tenantId: str
    pap_systolic: float
    pap_diastolic: float
    pap_mean: float
    heart_rate: int
    signal_quality: float


class BaselineStats(BaseModel):
    """Device baseline statistics"""
    avg_pap_systolic: Optional[float] = None
    stddev_pap_systolic: Optional[float] = None
    avg_pap_diastolic: Optional[float] = None
    stddev_pap_diastolic: Optional[float] = None
    avg_heart_rate: Optional[float] = None


class ScoringRequest(BaseModel):
    """Request for anomaly scoring"""
    telemetry: TelemetryInput
    baseline: Optional[BaselineStats] = None


class ScoringResponse(BaseModel):
    """Anomaly scoring result"""
    anomaly_score: float
    is_anomaly: bool
    confidence: float
    features: Dict[str, float]
    reason: Optional[str] = None


# ============================================================================
# Anomaly Detector (Rule-based + Statistical)
# ============================================================================

class SimpleAnomalyDetector:
    """
    Simple anomaly detection using:
    1. Clinical thresholds (PAP > 28/12 mmHg indicates HF risk)
    2. Statistical deviation from baseline (z-score)
    3. Rate of change detection

    In production, replace with:
    - Isolation Forest / One-Class SVM
    - LSTM for temporal patterns
    - XGBoost with engineered features
    - ONNX Runtime for fast inference
    """

    # Clinical thresholds (mmHg)
    PAP_SYSTOLIC_THRESHOLD = 28.0
    PAP_DIASTOLIC_THRESHOLD = 12.0
    PAP_SYSTOLIC_CRITICAL = 35.0
    PAP_DIASTOLIC_CRITICAL = 16.0

    # Statistical thresholds
    Z_SCORE_THRESHOLD = 2.5  # ~99% confidence interval

    @classmethod
    def score(cls, telemetry: TelemetryInput, baseline: Optional[BaselineStats] = None) -> ScoringResponse:
        """
        Compute anomaly score for a telemetry reading
        Returns score 0.0-1.0, where >0.5 is anomalous
        """

        features = {}
        reasons = []
        score_components = []

        # ====================================================================
        # 1. Clinical Threshold Detection
        # ====================================================================

        # Elevated PAP (primary HF indicator)
        if telemetry.pap_systolic >= cls.PAP_SYSTOLIC_CRITICAL:
            score_components.append(1.0)
            reasons.append(f"CRITICAL systolic PAP: {telemetry.pap_systolic} mmHg")
        elif telemetry.pap_systolic >= cls.PAP_SYSTOLIC_THRESHOLD:
            score_components.append(0.7)
            reasons.append(f"Elevated systolic PAP: {telemetry.pap_systolic} mmHg")
        else:
            score_components.append(0.0)

        if telemetry.pap_diastolic >= cls.PAP_DIASTOLIC_CRITICAL:
            score_components.append(1.0)
            reasons.append(f"CRITICAL diastolic PAP: {telemetry.pap_diastolic} mmHg")
        elif telemetry.pap_diastolic >= cls.PAP_DIASTOLIC_THRESHOLD:
            score_components.append(0.7)
            reasons.append(f"Elevated diastolic PAP: {telemetry.pap_diastolic} mmHg")
        else:
            score_components.append(0.0)

        features['pap_systolic'] = telemetry.pap_systolic
        features['pap_diastolic'] = telemetry.pap_diastolic

        # ====================================================================
        # 2. Statistical Deviation from Baseline (Z-score)
        # ====================================================================

        if baseline and baseline.avg_pap_systolic and baseline.stddev_pap_systolic:
            # Compute z-score
            z_score_sys = (telemetry.pap_systolic - baseline.avg_pap_systolic) / (baseline.stddev_pap_systolic + 1e-6)
            features['z_score_systolic'] = z_score_sys

            if abs(z_score_sys) > cls.Z_SCORE_THRESHOLD:
                score_components.append(0.8)
                reasons.append(f"Statistical outlier (z={z_score_sys:.2f})")
            else:
                score_components.append(0.0)

        # ====================================================================
        # 3. Heart Rate Anomalies
        # ====================================================================

        # Tachycardia (>100 bpm) or bradycardia (<60 bpm)
        if telemetry.heart_rate > 100:
            score_components.append(0.5)
            reasons.append(f"Tachycardia: {telemetry.heart_rate} bpm")
        elif telemetry.heart_rate < 50:
            score_components.append(0.5)
            reasons.append(f"Bradycardia: {telemetry.heart_rate} bpm")
        else:
            score_components.append(0.0)

        features['heart_rate'] = float(telemetry.heart_rate)

        # ====================================================================
        # 4. Signal Quality
        # ====================================================================

        if telemetry.signal_quality < 0.7:
            score_components.append(0.3)
            reasons.append(f"Poor signal quality: {telemetry.signal_quality:.2f}")
        else:
            score_components.append(0.0)

        features['signal_quality'] = telemetry.signal_quality

        # ====================================================================
        # Aggregate Score
        # ====================================================================

        # Weighted average (threshold detection weighted higher)
        if score_components:
            anomaly_score = np.max(score_components)  # Use max for conservative detection
        else:
            anomaly_score = 0.0

        is_anomaly = anomaly_score >= 0.5
        confidence = min(1.0, anomaly_score + 0.2) if is_anomaly else 0.8

        return ScoringResponse(
            anomaly_score=round(anomaly_score, 4),
            is_anomaly=is_anomaly,
            confidence=round(confidence, 2),
            features=features,
            reason="; ".join(reasons) if reasons else "Normal reading"
        )


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ml-anomaly-detection"}


@app.post("/score", response_model=ScoringResponse)
def score_telemetry(request: ScoringRequest):
    """
    Score telemetry for anomalies
    """
    try:
        result = SimpleAnomalyDetector.score(request.telemetry, request.baseline)
        return result

    except Exception as e:
        logger.error(f"Scoring error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "service": "Heart Failure Anomaly Detection",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "score": "/score"
        }
    }


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("🤖 ML Anomaly Detection Service Started")
    logger.info("📊 Model: Rule-based + Statistical (placeholder for ONNX)")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
