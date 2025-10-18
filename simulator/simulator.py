#!/usr/bin/env python3
"""
Heart Failure Device Simulator
Simulates CardioMEMS HF-class devices publishing telemetry to MQTT broker
Multi-tenant aware with realistic physiological data patterns
"""

import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Dict

import numpy as np
import paho.mqtt.client as mqtt
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

class SimulatorConfig(BaseModel):
    """Simulator configuration from environment variables"""
    mqtt_broker_host: str = Field(default="emqx", alias="MQTT_BROKER_HOST")
    mqtt_broker_port: int = Field(default=1883, alias="MQTT_BROKER_PORT")
    mqtt_username: str = Field(default="", alias="MQTT_USERNAME")
    mqtt_password: str = Field(default="", alias="MQTT_PASSWORD")

    device_count: int = Field(default=500, alias="DEVICE_COUNT")
    message_interval: int = Field(default=60, alias="MESSAGE_INTERVAL")
    tenants: List[str] = Field(default=["clinic-alpha", "hospital-beta"], alias="TENANTS")

    # Anomaly injection probability
    anomaly_probability: float = Field(default=0.05, alias="ANOMALY_PROBABILITY")

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        env_config = {
            "MQTT_BROKER_HOST": os.getenv("MQTT_BROKER_HOST", "emqx"),
            "MQTT_BROKER_PORT": int(os.getenv("MQTT_BROKER_PORT", "1883")),
            "MQTT_USERNAME": os.getenv("MQTT_USERNAME", ""),
            "MQTT_PASSWORD": os.getenv("MQTT_PASSWORD", ""),
            "DEVICE_COUNT": int(os.getenv("DEVICE_COUNT", "500")),
            "MESSAGE_INTERVAL": int(os.getenv("MESSAGE_INTERVAL", "60")),
            "TENANTS": os.getenv("TENANTS", "clinic-alpha,hospital-beta").split(","),
            "ANOMALY_PROBABILITY": float(os.getenv("ANOMALY_PROBABILITY", "0.05")),
        }
        return cls(**env_config)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class CardioMEMSReading:
    """
    CardioMEMS HF telemetry payload
    Represents pulmonary artery pressure readings from implanted sensor
    """
    timestamp: str
    deviceId: str
    tenantId: str

    # Pulmonary Artery Pressure (PAP) - primary HF indicator
    pap_systolic: float    # Normal: 15-28 mmHg, HF risk: >28 mmHg
    pap_diastolic: float   # Normal: 5-12 mmHg, HF risk: >12 mmHg
    pap_mean: float        # Computed: (systolic + 2*diastolic) / 3

    # Contextual vitals
    heart_rate: int        # Normal: 60-100 bpm
    signal_quality: float  # 0.0-1.0, >0.8 is good

    # Device metadata
    battery_level: int     # 0-100%
    temperature: float     # Celsius

    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps(asdict(self))


# ============================================================================
# Physiological Simulation
# ============================================================================

class PatientSimulator:
    """
    Simulates realistic CardioMEMS readings for a single patient/device
    Models normal variation + occasional anomalies
    """

    def __init__(self, device_id: str, tenant_id: str, baseline_risk: str = "normal"):
        self.device_id = device_id
        self.tenant_id = tenant_id
        self.baseline_risk = baseline_risk  # "normal", "mild", "moderate", "severe"

        # Baseline PAP values (mmHg)
        self.baseline_systolic = self._get_baseline_systolic()
        self.baseline_diastolic = self._get_baseline_diastolic()

        # Baseline heart rate (bpm)
        self.baseline_hr = random.randint(65, 85)

        # Device state
        self.battery_level = random.randint(80, 100)
        self.battery_drain_rate = 0.001  # ~1% per 1000 readings

    def _get_baseline_systolic(self) -> float:
        """Get baseline systolic PAP based on risk profile"""
        if self.baseline_risk == "normal":
            return random.uniform(18, 25)
        elif self.baseline_risk == "mild":
            return random.uniform(25, 30)
        elif self.baseline_risk == "moderate":
            return random.uniform(30, 35)
        else:  # severe
            return random.uniform(35, 45)

    def _get_baseline_diastolic(self) -> float:
        """Get baseline diastolic PAP based on risk profile"""
        if self.baseline_risk == "normal":
            return random.uniform(6, 10)
        elif self.baseline_risk == "mild":
            return random.uniform(10, 13)
        elif self.baseline_risk == "moderate":
            return random.uniform(13, 16)
        else:  # severe
            return random.uniform(16, 22)

    def generate_reading(self, inject_anomaly: bool = False) -> CardioMEMSReading:
        """Generate a single telemetry reading"""

        # Add realistic physiological noise
        noise_systolic = np.random.normal(0, 2.0)
        noise_diastolic = np.random.normal(0, 1.5)

        pap_systolic = self.baseline_systolic + noise_systolic
        pap_diastolic = self.baseline_diastolic + noise_diastolic

        # Inject anomaly (sudden PAP spike)
        if inject_anomaly:
            pap_systolic += random.uniform(10, 20)
            pap_diastolic += random.uniform(5, 10)
            logger.info(f"💥 Injected anomaly for {self.device_id}: systolic={pap_systolic:.1f}")

        # Compute mean PAP
        pap_mean = (pap_systolic + 2 * pap_diastolic) / 3

        # Heart rate with natural variation
        hr_variation = random.randint(-5, 10)
        heart_rate = max(50, min(120, self.baseline_hr + hr_variation))

        # Signal quality (occasional degradation)
        signal_quality = random.uniform(0.85, 1.0) if random.random() > 0.1 else random.uniform(0.6, 0.85)

        # Update battery
        self.battery_level = max(0, self.battery_level - self.battery_drain_rate)

        # Device temperature
        temperature = random.uniform(36.5, 37.2)

        return CardioMEMSReading(
            timestamp=datetime.now(timezone.utc).isoformat(),
            deviceId=self.device_id,
            tenantId=self.tenant_id,
            pap_systolic=round(pap_systolic, 2),
            pap_diastolic=round(pap_diastolic, 2),
            pap_mean=round(pap_mean, 2),
            heart_rate=heart_rate,
            signal_quality=round(signal_quality, 3),
            battery_level=int(self.battery_level),
            temperature=round(temperature, 2)
        )


# ============================================================================
# MQTT Client
# ============================================================================

class MQTTPublisher:
    """MQTT publisher for device telemetry"""

    def __init__(self, config: SimulatorConfig):
        self.config = config
        self.client = mqtt.Client(client_id=f"simulator-{random.randint(1000, 9999)}")

        # Set username/password if provided
        if config.mqtt_username and config.mqtt_password:
            self.client.username_pw_set(config.mqtt_username, config.mqtt_password)

        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        self.connected = False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"✅ Connected to MQTT broker at {self.config.mqtt_broker_host}:{self.config.mqtt_broker_port}")
        else:
            logger.error(f"❌ Failed to connect to MQTT broker, return code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.warning(f"⚠️  Disconnected from MQTT broker, return code: {rc}")

    def _on_publish(self, client, userdata, mid):
        # logger.debug(f"Published message {mid}")
        pass

    def connect(self):
        """Connect to MQTT broker with retry logic"""
        max_retries = 10
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to MQTT broker at {self.config.mqtt_broker_host}:{self.config.mqtt_broker_port}...")
                self.client.connect(self.config.mqtt_broker_host, self.config.mqtt_broker_port, 60)
                self.client.loop_start()

                # Wait for connection
                timeout = 10
                elapsed = 0
                while not self.connected and elapsed < timeout:
                    time.sleep(0.5)
                    elapsed += 0.5

                if self.connected:
                    return True
                else:
                    raise Exception("Connection timeout")

            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)

        return False

    def publish(self, tenant_id: str, device_id: str, payload: str):
        """Publish telemetry message"""
        topic = f"tenants/{tenant_id}/devices/{device_id}/telemetry"
        result = self.client.publish(topic, payload, qos=1)
        return result

    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()


# ============================================================================
# Main Simulator
# ============================================================================

class DeviceSimulator:
    """Orchestrates multiple device simulations"""

    def __init__(self, config: SimulatorConfig):
        self.config = config
        self.publisher = MQTTPublisher(config)
        self.devices: List[PatientSimulator] = []

    def initialize_devices(self):
        """Create virtual devices across tenants"""
        logger.info(f"Initializing {self.config.device_count} virtual devices across {len(self.config.tenants)} tenants...")

        devices_per_tenant = self.config.device_count // len(self.config.tenants)

        for tenant_idx, tenant_id in enumerate(self.config.tenants):
            for i in range(devices_per_tenant):
                device_num = (tenant_idx * devices_per_tenant) + i + 1
                device_id = f"CM-{tenant_id.upper().split('-')[0][:4]}-{device_num:03d}"

                # Assign risk profiles: 70% normal, 20% mild, 8% moderate, 2% severe
                risk_rand = random.random()
                if risk_rand < 0.70:
                    risk = "normal"
                elif risk_rand < 0.90:
                    risk = "mild"
                elif risk_rand < 0.98:
                    risk = "moderate"
                else:
                    risk = "severe"

                device = PatientSimulator(device_id, tenant_id, baseline_risk=risk)
                self.devices.append(device)

        logger.info(f"✅ Initialized {len(self.devices)} devices")

    def run(self):
        """Main simulation loop"""
        # Connect to MQTT
        if not self.publisher.connect():
            logger.error("Failed to connect to MQTT broker. Exiting.")
            sys.exit(1)

        # Initialize devices
        self.initialize_devices()

        logger.info(f"📡 Starting telemetry simulation (interval: {self.config.message_interval}s)")
        logger.info(f"🎯 Anomaly injection probability: {self.config.anomaly_probability * 100}%")

        message_count = 0

        try:
            while True:
                start_time = time.time()

                # Generate and publish readings for all devices
                for device in self.devices:
                    # Randomly inject anomalies
                    inject_anomaly = random.random() < self.config.anomaly_probability

                    reading = device.generate_reading(inject_anomaly=inject_anomaly)
                    payload = reading.to_json()

                    self.publisher.publish(reading.tenantId, reading.deviceId, payload)
                    message_count += 1

                elapsed = time.time() - start_time
                logger.info(f"📤 Published {len(self.devices)} messages in {elapsed:.2f}s (total: {message_count})")

                # Sleep until next interval
                sleep_time = max(0, self.config.message_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("⛔ Received interrupt signal. Shutting down...")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        finally:
            self.publisher.disconnect()
            logger.info("👋 Simulator stopped")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    logger.info("🏥 Heart Failure Device Simulator Starting...")

    config = SimulatorConfig.from_env()
    logger.info(f"Configuration: {config.model_dump()}")

    simulator = DeviceSimulator(config)
    simulator.run()
