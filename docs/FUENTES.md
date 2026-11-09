# Fuentes oficiales

Consulta web: 2026-11-09. La consulta documental no prueba el estado del gateway.

- RAKWireless, repositorio oficial: https://github.com/RAKWireless/rak_common_for_gateway
- RAKWireless, instalación Raspberry Pi/concentradores: https://docs.rakwireless.com/Knowledge-Hub/Learn/Raspberry-Pi-and-RAK-LPWAN-Concentrators/
- RAKWireless, selección SPI del RAK5146 en instalador: https://github.com/RAKWireless/rak_common_for_gateway/blob/master/lora/install_normal.sh
- The Things Stack, diagnóstico de gateway y TX_ACK: https://www.thethingsindustries.com/docs/hardware/gateways/troubleshooting/
- The Things Stack, Gateway Server y programación de downlinks: https://www.thethingsindustries.com/docs/concepts/architecture/components/gateway-server/

Inferencia pendiente de pruebas: separar hilos downstream no garantiza ausencia de latencia si el receptor compartido espera otras operaciones. Las restricciones temporales de downlink deben medirse; modificar rxpk.time no demuestra recuperación de ventanas de recepción.
