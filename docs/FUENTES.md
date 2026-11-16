# Fuentes oficiales

Consulta web: 2026-11-09. La consulta documental no prueba el estado del gateway.

- RAKWireless, repositorio oficial: https://github.com/RAKWireless/rak_common_for_gateway
- RAKWireless, instalación Raspberry Pi/concentradores: https://docs.rakwireless.com/Knowledge-Hub/Learn/Raspberry-Pi-and-RAK-LPWAN-Concentrators/
- RAKWireless, selección SPI del RAK5146 en instalador: https://github.com/RAKWireless/rak_common_for_gateway/blob/master/lora/install_normal.sh
- The Things Stack, diagnóstico de gateway y TX_ACK: https://www.thethingsindustries.com/docs/hardware/gateways/troubleshooting/
- The Things Stack, Gateway Server y programación de downlinks: https://www.thethingsindustries.com/docs/concepts/architecture/components/gateway-server/

Inferencia pendiente de pruebas: separar hilos downstream no garantiza ausencia de latencia si el receptor compartido espera otras operaciones. Las restricciones temporales de downlink deben medirse; modificar rxpk.time no demuestra recuperación de ventanas de recepción.


## PROMPT 014 — Identidad y Join Accept

Consultadas para la auditoría, no son evidencia operacional de Raspberry:
- LoRa Alliance, TS001-1.0.4, secciones 6.2.5/6.2.6: https://lora-alliance.org/wp-content/uploads/2021/11/LoRaWAN-Link-Layer-Specification-v1.0.4.pdf (Join Request DevEUI; Join Accept contiene DevAddr cifrado).
- Semtech Learning Center, Network Server Sends Join Accept: https://learn.semtech.com/mod/book/view.php?chapterid=96&id=171 (campos Join Accept cifrados con AppKey en el procedimiento 1.0.4).
No implica que el nodo real use una versión ya verificada ni autoriza descifrado/almacenamiento de downlinks. La ausencia de claves y metadata de asignación en el dashboard es evidencia de código local.
