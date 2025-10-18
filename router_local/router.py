#!/usr/bin/env python3
"""
Local MQTT Router Service
Mimics AWS IoT Core Rules Engine for local development
- Subscribes to all tenant telemetry topics
- Validates and parses messages
- Stores in TimescaleDB
- Routes to ML service for anomaly scoring
"""

import json
import logging
import os
import re
import sys
import time
from typing import Optional, Dict, Any

import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ValidationError, Field
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

class RouterConfig(BaseModel):
    """Router configuration"""
    mqtt_broker_host: str = Field(default="emqx")
    mqtt_broker_port: int = Field(default=1883)
    mqtt_username: str = Field(default="")
    mqtt_password: str = Field(default="")

    database_url: str
    ml_service_url: str = Field(default="http://ml_service:8000")

    @classmethod
    def from_env(cls):
        return cls(
            mqtt_broker_host=os.getenv("MQTT_BROKER_HOST", "emqx"),
            mqtt_broker_port=int(os.getenv("MQTT_BROKER_PORT", "1883")),
            mqtt_username=os.getenv("MQTT_USERNAME", ""),
            mqtt_password=os.getenv("MQTT_PASSWORD", ""),
            database_url=os.getenv("DATABASE_URL"),
            ml_service_url=os.getenv("ML_SERVICE_URL", "http://ml_service:8000"),
        )


# ============================================================================
# Data Models
# ============================================================================

class TelemetryMessage(BaseModel):
    """Validated telemetry message schema"""
    timestamp: str
    deviceId: str
    tenantId: str

    pap_systolic: float
    pap_diastolic: float
    pap_mean: float
    heart_rate: int
    signal_quality: float

    battery_level: int
    temperature: float

    class Config:
        extra = "allow"  # Allow additional fields


# ============================================================================
# Topic Parser
# ============================================================================

class TopicParser:
    """Parse AWS IoT Core style MQTT topics"""

    TOPIC_PATTERN = re.compile(r'^tenants/(?P<tenant_id>[^/]+)/devices/(?P<device_id>[^/]+)/telemetry$')

    @classmethod
    def parse(cls, topic: str) -> Optional[Dict[str, str]]:
        """
        Parse topic and extract tenant_id and device_id
        Expected format: tenants/{tenantId}/devices/{deviceId}/telemetry
        """
        match = cls.TOPIC_PATTERN.match(topic)
        if match:
            return match.groupdict()
        return None


# ============================================================================
# Database Handler
# ============================================================================

class DatabaseHandler:
    """Handle TimescaleDB operations"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.conn = None
        self._connect()

    def _connect(self):
        """Connect to database with retry logic"""
        max_retries = 10
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to TimescaleDB (attempt {attempt + 1}/{max_retries})...")
                self.conn = psycopg2.connect(self.connection_string)
                logger.info("✅ Connected to TimescaleDB")
                return
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        raise Exception("Failed to connect to database after all retries")

    def insert_telemetry(self, msg: TelemetryMessage) -> bool:
        """Insert telemetry record into database"""
        try:
            with self.conn.cursor() as cur:
                # Update device last_seen
                cur.execute("""
                    INSERT INTO public.devices (device_id, tenant_id, last_seen_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (device_id)
                    DO UPDATE SET last_seen_at = NOW()
                """, (msg.deviceId, msg.tenantId))

                # Validate PAP ranges
                is_valid = (
                    15 <= msg.pap_systolic <= 100 and
                    5 <= msg.pap_diastolic <= 50 and
                    msg.pap_systolic > msg.pap_diastolic
                )

                validation_errors = None
                if not is_valid:
                    validation_errors = json.dumps({
                        "error": "PAP values out of physiological range",
                        "systolic": msg.pap_systolic,
                        "diastolic": msg.pap_diastolic
                    })

                # Insert telemetry
                cur.execute("""
                    INSERT INTO telemetry.heart_failure_measurements (
                        time, device_id, tenant_id,
                        pap_systolic, pap_diastolic, pap_mean,
                        heart_rate, signal_quality,
                        battery_level, temperature,
                        is_valid, validation_errors,
                        raw_payload
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s
                    )
                """, (
                    msg.timestamp, msg.deviceId, msg.tenantId,
                    msg.pap_systolic, msg.pap_diastolic, msg.pap_mean,
                    msg.heart_rate, msg.signal_quality,
                    msg.battery_level, msg.temperature,
                    is_valid, validation_errors,
                    json.dumps(msg.model_dump())
                ))

            self.conn.commit()
            return True

        except Exception as e:
            logger.error(f"Database insert failed: {e}")
            self.conn.rollback()
            return False

    def get_device_baseline(self, device_id: str, tenant_id: str, lookback_hours: int = 24) -> Optional[Dict[str, float]]:
        """Get baseline statistics for a device (for ML feature engineering)"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        AVG(pap_systolic) as avg_pap_systolic,
                        STDDEV(pap_systolic) as stddev_pap_systolic,
                        AVG(pap_diastolic) as avg_pap_diastolic,
                        STDDEV(pap_diastolic) as stddev_pap_diastolic,
                        AVG(heart_rate) as avg_heart_rate
                    FROM telemetry.heart_failure_measurements
                    WHERE device_id = %s
                      AND tenant_id = %s
                      AND time > NOW() - INTERVAL '%s hours'
                      AND is_valid = TRUE
                """, (device_id, tenant_id, lookback_hours))

                result = cur.fetchone()
                if result:
                    # Convert Decimal to float for JSON serialization
                    return {k: float(v) if v is not None else None for k, v in dict(result).items()}
                return None

        except Exception as e:
            logger.error(f"Failed to get device baseline: {e}")
            return None

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


# ============================================================================
# ML Service Client
# ============================================================================

class MLServiceClient:
    """Client for ML anomaly detection service"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

    def score(self, telemetry: TelemetryMessage, baseline: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Send telemetry to ML service for anomaly scoring
        Returns: {"anomaly_score": float, "is_anomaly": bool, "confidence": float}
        """
        try:
            payload = {
                "telemetry": telemetry.model_dump(),
                "baseline": baseline or {}
            }

            response = self.session.post(
                f"{self.base_url}/score",
                json=payload,
                timeout=2.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"ML service returned {response.status_code}: {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.warning("ML service timeout")
            return None
        except Exception as e:
            logger.error(f"ML service error: {e}")
            return None


# ============================================================================
# MQTT Router
# ============================================================================

class TelemetryRouter:
    """Main router that processes MQTT messages"""

    def __init__(self, config: RouterConfig):
        self.config = config
        self.db = DatabaseHandler(config.database_url)
        self.ml_client = MLServiceClient(config.ml_service_url)

        # MQTT client
        self.mqtt_client = mqtt.Client(client_id="router-service")
        if config.mqtt_username and config.mqtt_password:
            self.mqtt_client.username_pw_set(config.mqtt_username, config.mqtt_password)

        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_disconnect = self._on_disconnect

        self.message_count = 0
        self.error_count = 0

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            logger.info("✅ Router connected to MQTT broker")
            # Subscribe to all tenant telemetry topics
            client.subscribe("tenants/+/devices/+/telemetry")
            logger.info("📡 Subscribed to: tenants/+/devices/+/telemetry")
        else:
            logger.error(f"❌ Router connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        logger.warning(f"⚠️  Router disconnected from MQTT broker (rc={rc})")

    def _on_message(self, client, userdata, msg):
        """Process incoming MQTT message"""
        try:
            # Parse topic
            topic_info = TopicParser.parse(msg.topic)
            if not topic_info:
                logger.warning(f"Invalid topic format: {msg.topic}")
                self.error_count += 1
                return

            # Parse and validate payload
            try:
                payload = json.loads(msg.payload.decode('utf-8'))
                telemetry = TelemetryMessage(**payload)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"Invalid message payload: {e}")
                self.error_count += 1
                return

            # Verify tenant_id and device_id match topic
            if telemetry.tenantId != topic_info['tenant_id'] or telemetry.deviceId != topic_info['device_id']:
                logger.warning(f"Tenant/Device ID mismatch: topic={topic_info}, payload={telemetry.tenantId}/{telemetry.deviceId}")
                self.error_count += 1
                return

            # Store in database
            success = self.db.insert_telemetry(telemetry)
            if not success:
                self.error_count += 1
                return

            # Get baseline stats for ML
            baseline = self.db.get_device_baseline(telemetry.deviceId, telemetry.tenantId)

            # Score with ML service (async, non-blocking)
            ml_result = self.ml_client.score(telemetry, baseline)
            if ml_result and ml_result.get('is_anomaly'):
                logger.warning(
                    f"🚨 ANOMALY DETECTED: {telemetry.deviceId} | "
                    f"Score: {ml_result.get('anomaly_score', 0):.3f} | "
                    f"PAP: {telemetry.pap_systolic}/{telemetry.pap_diastolic} mmHg"
                )
                # In production: publish to SNS/SQS, store alert in DB

            self.message_count += 1

            if self.message_count % 100 == 0:
                logger.info(f"📊 Processed {self.message_count} messages (errors: {self.error_count})")

        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}", exc_info=True)
            self.error_count += 1

    def connect(self):
        """Connect to MQTT broker"""
        max_retries = 10
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to MQTT broker at {self.config.mqtt_broker_host}:{self.config.mqtt_broker_port}...")
                self.mqtt_client.connect(self.config.mqtt_broker_host, self.config.mqtt_broker_port, 60)
                return True
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        return False

    def run(self):
        """Start the router main loop"""
        if not self.connect():
            logger.error("Failed to connect to MQTT broker. Exiting.")
            sys.exit(1)

        logger.info("🚀 Router service started")

        try:
            self.mqtt_client.loop_forever()
        except KeyboardInterrupt:
            logger.info("⛔ Received interrupt signal")
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
        finally:
            self.mqtt_client.disconnect()
            self.db.close()
            logger.info("👋 Router service stopped")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    logger.info("🔀 Local IoT Router Service Starting...")

    config = RouterConfig.from_env()
    logger.info(f"Configuration: MQTT={config.mqtt_broker_host}:{config.mqtt_broker_port}")

    router = TelemetryRouter(config)
    router.run()
