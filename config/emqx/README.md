# EMQX Configuration

EMQX configuration files can be placed here to customize the MQTT broker.

For local dev, the default configuration is sufficient.

For production AWS IoT Core, see `infrastructure/iot_core.tf`.

## Useful EMQX Settings

- Auth plugins (JWT, PostgreSQL)
- ACL rules (topic permissions)
- Webhook integrations
- Rule engine (bridge to TimescaleDB)

See: https://www.emqx.io/docs/en/v5.0/configuration/configuration.html
