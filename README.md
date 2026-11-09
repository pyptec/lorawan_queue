# Gateway LoRaWAN: Raspberry Pi 4 + RAK5146 SPI

## Estado y alcance

FASE 1: estructura documental preparada. Operación del gateway: PENDIENTE de verificación en Raspberry Pi. Este repositorio contiene un proxy Semtech UDP en Python con SQLite; no demuestra por sí solo que la recepción RF, TTN o los reenvíos funcionen.

Código base revisado: `a4a4cd64ae7096936fd02d897ac8e57ee5ad7e2e`, rama `main`. La versión anterior del README se conserva en [docs/README_PREVIO.md](docs/README_PREVIO.md) como antecedente; sus afirmaciones operativas no constituyen pruebas.

## Documentación

- [Bitácora y registro de intervenciones](BITACORA.md).
- [Reglas permanentes](AGENTS.md).
- [Arquitectura, requisitos y diferencias actuales](docs/ARQUITECTURA.md).
- [Plan por fases y verificaciones](docs/PLAN_VALIDACION.md).
- [Fuentes oficiales](docs/FUENTES.md).

## Instalación reproducible: procedimiento pendiente de ejecución

1. Registrar modelo de Raspberry Pi, sistema operativo, revisión del RAK5146, HAT, conexión SPI, alimentación, antena y repositorio/commit instalado. No transmitir sin verificar hardware y antena.
2. Usar el [repositorio oficial RAKWireless](https://github.com/RAKWireless/rak_common_for_gateway) y su [guía oficial](https://docs.rakwireless.com/Knowledge-Hub/Learn/Raspberry-Pi-and-RAK-LPWAN-Concentrators/). Registrar el commit seleccionado y seguir las instrucciones correspondientes al hardware y sistema reales. No ejecutar el instalador sobre el gateway operativo antes de revisar su configuración y respaldo.
3. Verificar SPI, servicio del packet forwarder y configuración efectiva. Identificar AU915 y el bloque exacto de los dispositivos; todavía no se conoce ese bloque. No asumir una subbanda.
4. Verificar EUI, registro del gateway, cluster TTN, plan de frecuencias y eventos en la consola. No deducir conectividad por el hostname configurado.
5. Solo después de las verificaciones, evaluar el proxy y su despliegue. Conservar un respaldo de configuración y base de datos antes de cambios.

## Configuración observada en el código

| Parámetro | Valor local observado |
|---|---|
| Escucha | `127.0.0.1:1700` |
| Destino | `nam1.cloud.thethings.network:1700` |
| SQLite | `/home/pi/lorawan_queue/lorawan_queue.db` |
| Espera ACK | 2 segundos |
| Lote | 10 paquetes |
| Espera sin pendientes | 5 segundos |
| Reintento | pausas de 60 segundos en el worker |

La constante `RETRY_INTERVAL` existe, pero las pausas de fallo usan literalmente `60`. Estos valores describen el archivo local, no la configuración activa de la Raspberry.

El programa utiliza la biblioteca estándar de Python. Comando de arranque previsto en Raspberry, no ejecutado en esta intervención:

```bash
python3 lorawan_queue.py
```

El módulo abre sockets al importarse; no importarlo para comprobar sintaxis. No se ha instalado ni validado un servicio systemd. FastAPI y dashboard corresponden a fases posteriores.

## Operación y límites actuales

Se conserva el datagrama recibido en `raw_packet`; el worker modifica `rxpk[].time` en la copia enviada. Solo hay transiciones implementadas a `pending` y `sent`. `failed` es un requisito pendiente. `sent` significa que el programa recibió un PUSH_ACK con token coincidente; no prueba entrega a la aplicación final.

No se promete recuperación completa mediante reenvío UDP tardío. La aceptación por TTN, los contadores de trama y la entrega final requieren pruebas. Conservar `time` no recupera ventanas RX1/RX2 vencidas. Los Join Request y mensajes que requieren respuesta inmediata necesitan tratamiento explícito en la auditoría.

No hay evidencia todavía de ausencia de retardos en downlinks: el receptor local también espera ACK de estadísticas y hace escrituras SQLite. Ver [arquitectura](docs/ARQUITECTURA.md).

## Flujo de cambios

Revisar código, configuración y estado real; identificar el problema; proponer cambio; modificar solo en el PC; validar localmente; commit; push; pull en Raspberry; validar allí; registrar evidencia. No registrar pasos pendientes como ejecutados. No modificar funciones existentes antes de reunir la evidencia requerida.
