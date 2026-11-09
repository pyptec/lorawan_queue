# Plan de validación

## Registro de fases

| Fase | Resultado registrado | Estado |
|---|---|---|
| 1 Documentación | Archivos preparados; ver BITACORA.md para validación y Git | PENDIENTE |
| 2 Gateway | Sin acceso ni evidencia remota | PENDIENTE |
| 3 TTN | Sin acceso ni eventos observados | PENDIENTE |
| 4 Cola | Hallazgos preliminares estáticos; auditoría no iniciada | PENDIENTE |
| 5 Sin Internet | No ejecutada | PENDIENTE |
| 6 Reenvío | No ejecutada | PENDIENTE |
| 7 Dashboard | No implementado | PENDIENTE |
| 8 Servicios | No desplegados ni inspeccionados | PENDIENTE |
| 9 Recuperación | No ejecutada | PENDIENTE |

## Evidencia requerida y criterios

1. Documentación: enlaces locales válidos, bitácora, reglas y plan; revisar diff, commit y push. Registrar su resultado antes de abrir FASE 2.
2. Gateway: modelo/OS, revisión hardware, SPI, alimentación, antena, commit RAK instalado, servicio real y logs. Registrar configuración activa, EUI y bloque AU915 cotejado con los nodos. Resultado: concentrador inicia y recibe RF con evidencia.
3. TTN: registro y cluster correctos, configuración coincidente, uplink observado en gateway y aplicación, downlink y Join Accept de control con tiempos y TX_ACK. Distinguir recepción UDP de entrega final.
4. Cola: inspeccionar esquema real en modo lectura, estados, tiempos por rxpk, deduplicación, fallos y concurrencia. Proponer cambios solo tras contrastar código/configuración/estado. Validar en PC antes de commit/push/pull y prueba remota.
5. Sin Internet: prueba acotada y reversible con acceso local disponible; documentar método de corte y restauración. Medir eventos emitidos/recibidos/guardados; payload y timestamp intactos. No ejecutar cortes desde esta fase documental.
6. Reenvío: restaurar red; correlacionar registros SQLite, ACK UDP y eventos de aplicación con identificador/conteo. Verificar timestamps, duplicados, pérdidas, contadores y comportamiento de Join Request. Un ACK aislado no basta. Medir downlinks durante backlog.
7. Dashboard: verificar cada métrica contra DB/logs y representar estados desconocidos. Definir seguridad de acceso antes de exponer FastAPI.
8. Servicios: revisar unidades existentes, usuario, permisos, rutas, orden de arranque, reinicios, logs y sincronización horaria. Documentar instalación y reversión.
9. Recuperación: reinicio del proceso y de Raspberry con pendientes; comprobar integridad SQLite, conservación temporal, recuperación y espacio en disco. Registrar límites y pérdidas si existen.

## Comandos sugeridos para Raspberry (NO ejecutados)

Primero identificar usuario, rutas y nombres de servicios; no asumir que el servicio se llama como el ejemplo.

```bash
hostnamectl
cat /etc/os-release
uname -a
ls -l /dev/spidev*
timedatectl status
systemctl list-units --type=service --all
systemctl list-unit-files --type=service
```

Después consultar la unidad identificada con `systemctl cat <unidad>` y `journalctl -u <unidad> --no-pager -n 100`; registrar exit codes y salidas pertinentes, sin secretos. Revisar `git status`, `git rev-parse HEAD` y configuración efectiva en las rutas identificadas. No ejecutar instaladores, cambiar región o reiniciar servicios durante una inspección.

## Plantilla de prueba

Fecha/zona; fase; objetivo; PC/Raspberry/TTN; versiones y commit; configuración relevante; condiciones iniciales; comando exacto; salida/exit code; resultado esperado y obtenido; artefactos; limitaciones; pendientes; estado permitido. No usar capturas simuladas como evidencia.
