"use strict";

// La interfaz solo presenta la API existente: sin acciones de administracion.
const $ = id => document.getElementById(id);
const unavailable = "NO DISPONIBLE";
const validNumber = n => typeof n === "number" && Number.isFinite(n);
const text = value => value === null || value === undefined || value === "" ? unavailable : String(value);
const count = n => validNumber(n) ? n.toLocaleString("es-CO") : "—";
const numeric = (n, unit = "", digits = 1) => validNumber(n) ? n.toLocaleString("es-CO", {maximumFractionDigits: digits}) + unit : "—";
const state = value => typeof value === "string" ? value : "UNKNOWN";
let lastData = null;
let selectedPacketId = null;
let eventFilter = "all";
let queueStamp = null;
let previousInternet = null;
let recovered = false;
let currentEvents = [];

function element(tag, className = "", value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = text(value);
  return node;
}
function icon(name, className = "icon") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", className);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#i-" + name);
  svg.append(use);
  return svg;
}
function badge(label, status = label) {
  const node = element("span", "badge", label);
  node.dataset.state = state(status);
  return node;
}
function empty(title, detail = "", graphic = "info") {
  const node = element("div", "empty-message");
  node.append(icon(graphic), element("span", "", title));
  if (detail) node.append(element("small", "", detail));
  return node;
}
function instant(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "string" && !/^\d{4}-\d{2}-\d{2}T/.test(value)) return null;
  const date = new Date(typeof value === "number" ? value * 1000 : value);
  return Number.isFinite(date.getTime()) ? date : null;
}
function dateText(value, withDate = false) {
  const date = instant(value);
  if (!date) return unavailable;
  return date.toLocaleString("es-CO", {timeZone: "America/Bogota", ...(withDate ? {day: "2-digit", month: "short"} : {}), hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false});
}
function bytes(value) {
  if (!validNumber(value)) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
  return numeric(value, " " + units[index]);
}
function uptime(value) {
  if (!validNumber(value)) return "—";
  const days = Math.floor(value / 86400), hours = Math.floor(value % 86400 / 3600), minutes = Math.floor(value % 3600 / 60);
  return days ? `${days} d ${hours} h` : `${hours} h ${minutes} min`;
}
function ackAge(value) {
  if (!validNumber(value) || value < 0) return unavailable;
  return value < 120 ? numeric(value, " s", 0) : uptime(value);
}
function threshold(value) {
  return !validNumber(value) ? "UNKNOWN" : value > 85 ? "CRITICAL" : value >= 70 ? "WARNING" : "OK";
}
function service(data, name) {
  return (Array.isArray(data.services) ? data.services : []).find(item => item.name === name) || {state: "UNKNOWN"};
}
function serviceLabel(item) {
  return item.ActiveState === "active" ? "ACTIVE" : item.ActiveState && item.ActiveState !== "UNKNOWN" ? String(item.ActiveState).toUpperCase() : "UNKNOWN";
}
function table(headers, bodyRows, className = "", label = "Tabla de datos") {
  const scroll = element("div", "scroll");
  scroll.tabIndex = 0;
  scroll.setAttribute("role", "region");
  scroll.setAttribute("aria-label", label);
  const grid = element("table", className);
  const head = element("thead"), tr = element("tr");
  headers.forEach(label => { const th = element("th", "", label); th.scope = "col"; tr.append(th); });
  head.append(tr);
  const body = element("tbody");
  bodyRows.forEach(row => body.append(row));
  grid.append(head, body);
  scroll.append(grid);
  return scroll;
}
function cell(row, value, className = "") {
  const td = element("td", className);
  td.append(value instanceof Node ? value : document.createTextNode(text(value)));
  row.append(td);
  return td;
}
function setMenu(open) {
  const mobile = window.matchMedia("(max-width:740px)").matches;
  document.body.classList.toggle("menu-open", mobile && open);
  $("sidebar").inert = mobile && !open;
  $("menu-toggle").setAttribute("aria-expanded", String(mobile && open));
  $("menu-scrim").hidden = !mobile || !open;
}
window.matchMedia("(max-width:740px)").addEventListener("change", () => setMenu(false));
function goTo(page, focus = false) {
  if (!$(page)?.classList.contains("page")) return;
  document.querySelectorAll(".page").forEach(section => { section.hidden = section.id !== page; });
  document.querySelectorAll(".nav-item").forEach(button => {
    const active = button.dataset.page === page;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
    if (!button.getAttribute("aria-label")) button.setAttribute("aria-label", button.textContent.trim());
  });
  setMenu(false);
  if (focus) $("main-content").focus({preventScroll: true});
}
document.querySelectorAll(".nav-item").forEach(button => button.addEventListener("click", () => goTo(button.dataset.page, true)));
document.querySelectorAll("[data-goto]").forEach(button => button.addEventListener("click", () => goTo(button.dataset.goto, true)));
document.querySelector(".brand").addEventListener("click", event => { event.preventDefault(); goTo("overview", true); });
$("menu-toggle").addEventListener("click", () => {
  const open = !document.body.classList.contains("menu-open");
  setMenu(open);
  if (open) document.querySelector(".nav-item.active").focus();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && document.body.classList.contains("menu-open")) {
    setMenu(false); $("menu-toggle").focus();
  }
});
document.addEventListener("click", event => {
  if (document.body.classList.contains("menu-open") && !event.target.closest(".sidebar, .menu-toggle")) {
    setMenu(false);
  }
});

function kpi(label, graphic, value, note, status = "", extra = null) {
  const card = element("article", "kpi"); card.dataset.state = status;
  const head = element("div", "kpi-top"), tile = element("span", "icon-tile"); tile.append(icon(graphic)); head.append(tile, element("span", "", label));
  const main = element("div", "kpi-value" + (value === "—" ? " no-data" : ""));
  main.append(value instanceof Node ? value : document.createTextNode(text(value)));
  card.append(head, main);
  if (extra) card.append(extra);
  card.append(element("p", "kpi-note", note));
  return card;
}
function queueStat(label, value, status = "") {
  const node = element("div", "queue-stat" + (!validNumber(value) ? " no-data" : ""));
  node.dataset.state = value > 0 ? status : "";
  node.append(element("small", "", label), element("strong", "", count(value)));
  return node;
}
function renderKpis(data, stale) {
  const system = data.system || {}, queue = data.queue || {}, summary = queue.summary || {}, internet = data.internet || {}, gateway = data.gateway || {};
  const ups = upsValue(data, stale);
  const qKnown = queue.state === "OK";
  const devices = Array.isArray(data.devices) ? data.devices : [];
  const identities = new Set(devices.map(item => item.identity).filter(Boolean));
  const gatewayState = stale || !data.system ? "UNKNOWN" : data.health === "OK" ? "ONLINE" : "DEGRADED";
  const queueInfo = element("div", "kpi-subvalue");
  const sent = element("span", ""); sent.append(element("strong", "", qKnown ? count(summary.sent) : "—"), document.createTextNode(" Sent")); queueInfo.append(sent);
  const pending = element("span", "queue-pending"); pending.append(element("strong", "", qKnown ? count(summary.pending) : "—"), document.createTextNode(" Pending"));
  const tempState = !validNumber(system.temperature_c) ? "UNKNOWN" : system.temperature_c >= 80 ? "CRITICAL" : system.temperature_c >= 70 ? "WARNING" : "OK";
  $("cards").replaceChildren(
    kpi("Gateway", "gateway", badge(gatewayState), "Salud general · RF independiente", gatewayState),
    kpi("Dispositivos detectados", "devices", qKnown ? count(identities.size) : "—", "Identidades en la muestra local", qKnown ? "" : "UNKNOWN"),
    kpi("Cola local", "database", pending, queue.state === "OK" ? "SQLite · uplinks persistidos" : "DB: NO DISPONIBLE", qKnown ? "" : "UNKNOWN", queueInfo),
    kpi("Internet", "internet", badge(stale ? "UNKNOWN" : state(internet.state)), "Pruebas DNS + TCP externo", stale ? "UNKNOWN" : state(internet.state)),
    kpi("TTN / servidor", "cloud", badge(stale ? "UNKNOWN" : state(gateway.ttn?.state)), "Evidencia PUSH_ACK UDP", stale ? "UNKNOWN" : state(gateway.ttn?.state)),
    upsKpi(ups),
    kpi("Temperatura CPU", "thermometer", numeric(system.temperature_c, " °C"), validNumber(system.temperature_c) ? "Temperatura del sistema" : "Fuente térmica no disponible", tempState)
  );
}
function flowStep(graphic, title, status, detail) {
  const node = element("div", "flow-step"); node.dataset.state = status;
  const illustration = element("div", "flow-illustration"); illustration.append(icon(graphic));
  node.append(illustration, element("h3", "", title), badge(status), element("p", "", detail));
  return node;
}
function flowLink(status, blocked = false) {
  const link = element("div", "flow-link"); link.dataset.state = status;
  link.setAttribute("aria-label", blocked ? "Ruta externa no disponible según conectividad" : "Evidencia de paso: " + status);
  link.append(icon(blocked ? "close" : "arrow"));
  return link;
}
function renderFlow(data, stale) {
  const queue = data.queue || {}, summary = queue.summary || {}, gateway = data.gateway || {}, internet = data.internet || {};
  const known = !stale && queue.state === "OK";
  const rf = stale ? "UNKNOWN" : state(gateway.rak5146?.state);
  const ttn = stale ? "UNKNOWN" : state(gateway.ttn?.state);
  const localStatus = !known ? "UNKNOWN" : summary.pending > 0 ? "pending" : "OK";
  const nodeCount = Array.isArray(data.devices) ? data.devices.length : 0;
  const pf = serviceLabel(service(data, "ttn-gateway.service"));
  const latest = (queue.rows || []).map(row => instant(row.received_at)?.getTime()).filter(validNumber);
  const age = validNumber(data.system?.time) && latest.length ? data.system.time * 1000 - Math.max(...latest) : null;
  const received = known && validNumber(age) && age >= 0 && age <= 120000;
  const blocked = !stale && internet.state === "OFFLINE";
  const linkState = blocked ? "OFFLINE" : !known ? "UNKNOWN" : summary.pending > 0 ? "pending" : ttn === "ONLINE" ? "OK" : "UNKNOWN";
  $("operational-flow").replaceChildren(
    flowStep("radio", "Dispositivo LoRaWAN", received ? "RECIBIDO" : "UNKNOWN", known && nodeCount ? "Metadatos rxpk disponibles" : "Sin recepción reciente verificada"),
    flowLink(received ? "OK" : "UNKNOWN"),
    flowStep("gateway", "Gateway RAK5146", rf, "Packet Forwarder: " + (stale ? "UNKNOWN" : pf)),
    flowLink(localStatus),
    flowStep("database", "Cola local SQLite", localStatus === "pending" ? "pending" : localStatus, known ? count(summary.pending) + " Pending · " + count(summary.sent) + " Sent" : "DB no disponible"),
    flowLink(linkState, blocked),
    flowStep("cloud", "TTN / servidor", ttn, validNumber(gateway.ttn?.ack_age_seconds) ? "Último ACK: " + ackAge(gateway.ttn.ack_age_seconds) : "Sin ACK UDP disponible")
  );
}
function resource(label, graphic, value, hint) {
  const node = element("div", "resource");
  const head = element("div", "resource-heading"); head.append(icon(graphic), document.createTextNode(label), element("strong", "", numeric(value, " %")));
  const meter = element("div", "meter"); meter.dataset.state = threshold(value);
  meter.setAttribute("role", "meter"); meter.setAttribute("aria-label", label);
  meter.setAttribute("aria-valuemin", "0"); meter.setAttribute("aria-valuemax", "100");
  if (validNumber(value)) meter.setAttribute("aria-valuenow", String(value)); else meter.setAttribute("aria-valuetext", unavailable);
  const fill = element("span"); fill.style.width = validNumber(value) ? Math.max(0, Math.min(100, value)) + "%" : "0%"; meter.append(fill);
  node.append(head, meter, element("p", "resource-hint", hint));
  return node;
}
function resources(system) {
  const node = element("div", "resource-bars");
  node.append(resource("CPU", "cpu", system.cpu_percent, "Carga del procesador"), resource("RAM", "ram", system.ram?.percent, bytes(system.ram?.used) + " / " + bytes(system.ram?.total)), resource("SD", "sd", system.disk?.percent, bytes(system.disk?.used) + " / " + bytes(system.disk?.total)));
  return node;
}
function statusItem(label, graphic, value) {
  const node = element("div", "status-item"), main = element("span", "status-value");
  main.append(value instanceof Node ? value : document.createTextNode(text(value)));
  node.append(icon(graphic), element("span", "label", label), main); return node;
}
function renderSystem(data, stale) {
  const system = data.system || {}, gateway = data.gateway || {}, internet = data.internet || {};
  const pf = service(data, "ttn-gateway.service"), pfLabel = stale ? "UNKNOWN" : serviceLabel(pf);
  const rows = element("div", "system-status-grid");
  rows.append(statusItem("Temperatura", "thermometer", numeric(system.temperature_c, " °C")), statusItem("Uptime", "clock", uptime(system.uptime_seconds)), statusItem("Internet", "internet", badge(stale ? "UNKNOWN" : state(internet.state))), statusItem("TTN", "cloud", badge(stale ? "UNKNOWN" : state(gateway.ttn?.state))), statusItem("Packet Forwarder", "services", badge(pfLabel)), statusItem("RAK5146 RF", "radio", badge(stale ? "UNKNOWN" : state(gateway.rak5146?.state))), statusItem("GPS", "gps", badge(stale ? "UNKNOWN" : state(gateway.gps?.state))), statusItem("Servicio cola", "database", badge(stale ? "UNKNOWN" : serviceLabel(service(data, "lorawan-queue.service")))));
  $("system-overview").replaceChildren(resources(system), rows);
  const details = element("div", "system-resources"); details.append(resources(system));
  const lan = Array.isArray(system.lan) ? system.lan.map(item => item.interface + " · " + item.ip).join(" / ") : null;
  details.append(detailList([["Hostname", system.hostname], ["Fecha y hora del sistema", dateText(system.time, true)], ["Uptime", uptime(system.uptime_seconds)], ["Temperatura CPU", numeric(system.temperature_c, " °C")], ["Frecuencia CPU", numeric(system.frequency_mhz, " MHz")], ["Load average", Array.isArray(system.load) ? system.load.map(n => numeric(n)).join(" / ") : null], ["RAM total / usada", bytes(system.ram?.total) + " / " + bytes(system.ram?.used)], ["RAM libre / disponible", bytes(system.ram?.free) + " / " + bytes(system.ram?.available)], ["SD total / usada", bytes(system.disk?.total) + " / " + bytes(system.disk?.used)], ["SD libre", bytes(system.disk?.free)], ["LAN · interfaces", lan || null], ["Gateway de red", system.network_gateway]]));
  $("system-detail").replaceChildren(details);
  const source = internet.dns === true ? "Resolución disponible" : internet.dns === false ? "Resolución fallida" : "UNKNOWN";
  $("gateway-detail").replaceChildren(detailList([["LAN", badge(stale ? "UNKNOWN" : state(system.lan_state))], ["Internet", badge(stale ? "UNKNOWN" : state(internet.state))], ["DNS", source], ["Fuente DNS", internet.dns_source], ["Prueba TCP", internet.tcp === true ? "Destino externo accesible" : internet.tcp === false ? "Destino sin respuesta" : null], ["TTN", badge(stale ? "UNKNOWN" : state(gateway.ttn?.state))], ["Edad del ACK UDP", numeric(gateway.ttn?.ack_age_seconds, " s", 0)], ["Packet Forwarder", badge(pfLabel)], ["RAK5146 RF", badge(stale ? "UNKNOWN" : state(gateway.rak5146?.state))], ["SPI", state(gateway.rak5146?.spi)], ["Plan", gateway.rak5146?.plan], ["GPS", badge(stale ? "UNKNOWN" : state(gateway.gps?.state))], ["Última muestra cola", dateText(data.updated_at?.queue, true)], ["Última muestra red", dateText(data.updated_at?.internet, true)]]));
  const serviceRows = (Array.isArray(data.services) ? data.services : []).map(item => {
    const row = element("tr"), identity = element("span"); identity.append(element("span", "service-name", item.name), element("small", "service-caption", item.source || "systemctl show"));
    cell(row, identity); cell(row, badge(stale ? "UNKNOWN" : serviceLabel(item))); cell(row, item.SubState); cell(row, item.MainPID, "mono"); cell(row, item.ActiveEnterTimestamp); cell(row, uptime(item.uptime_seconds)); cell(row, item.NRestarts); return row;
  });
  $("services").replaceChildren(serviceRows.length ? table(["Servicio", "Estado", "SubState", "PID", "Inicio", "Uptime", "Reinicios"], serviceRows, "", "Servicios systemd") : empty("Servicios no disponibles", "Esperando datos de systemd.", "services"));
}
function detailList(items) {
  const dl = element("dl", "detail-list");
  items.forEach(([label, value]) => { const row = element("div", "detail-row"), dd = element("dd"); dd.append(value instanceof Node ? value : document.createTextNode(text(value))); row.append(element("dt", "", label), dd); dl.append(row); });
  return dl;
}
function renderQueueSummary(queue) {
  const known = queue.state === "OK", summary = known ? queue.summary || {} : {};
  $("queue-status").replaceWith(Object.assign(badge(state(queue.state)), {id: "queue-status"}));
  const stats = element("div", "queue-stats"); stats.append(queueStat("Total", summary.total), queueStat("Sent", summary.sent, "sent"), queueStat("Pending", summary.pending, "pending"));
  const distribution = element("div", "queue-distribution"); distribution.setAttribute("aria-label", "Distribución de registros según estado");
  const keys = element("div", "distribution-key");
  for (const key of ["sent", "pending", "failed"]) {
    const part = element("span", key); part.style.width = summary.total > 0 && validNumber(summary[key]) ? Math.max(0, Math.min(100, summary[key] / summary.total * 100)) + "%" : "0%"; distribution.append(part);
    const legend = element("span"); legend.append(element("i", key), document.createTextNode(key + " " + count(summary[key]))); keys.append(legend);
  }
  const meta = element("div", "queue-meta");
  for (const [label, value] of [["Intentos", count(summary.attempts)], ["DB", bytes(queue.size_bytes)], ["Failed", count(summary.failed)]]) { const node = element("span"); node.append(document.createTextNode(label + " "), element("strong", "", value)); meta.append(node); }
  const note = element("p", "table-note", !known ? "DB: NO DISPONIBLE. No se crea una base desde el dashboard." : summary.total === 0 ? "Sin registros almacenados." : "Dato histórico no disponible. Autonomía: NO DISPONIBLE.");
  $("queue-overview").replaceChildren(stats, distribution, keys, meta, note);
  $("queue-summary").replaceChildren(...[["Total", summary.total, ""], ["Sent", summary.sent, "sent"], ["Pending", summary.pending, "pending"], ["Failed", summary.failed, "failed"], ["Intentos", summary.attempts, ""], ["Tamaño DB", queue.size_bytes, ""]].map(([label, value, kind]) => {
    const tile = element("div", "summary-tile");
    if (label === "Tamaño DB") { const stat = queueStat(label, value); stat.querySelector("strong").textContent = bytes(value); tile.append(stat); } else tile.append(queueStat(label, value, kind)); return tile;
  }));
}
function deviceIdentity(item) {
  const node = element("div", "device-identity"), labels = element("span");
  const name = item.registered === true && typeof item.name === "string" && item.name.trim() ? item.name : "DISPOSITIVO NO REGISTRADO";
  labels.append(element("strong", "device-name", name));
  if (item.description) labels.append(element("small", "", item.description));
  if (item.device_id) labels.append(element("small", "", "Device ID: " + item.device_id));
  else if (item.alias_device_id) labels.append(element("small", "", "Device ID (config.): " + item.alias_device_id));
  labels.append(element("small", "mono", item.dev_addr ? "DevAddr: " + item.dev_addr : item.identity || "Identificador no disponible"));
  if (item.dev_eui && !item.identity?.startsWith("DevEUI:")) labels.append(element("small", "mono", "DevEUI: " + item.dev_eui));
  if (!item.dev_eui && item.alias_dev_eui) labels.append(element("small", "mono", "DevEUI (config.): " + item.alias_dev_eui));
  if (item.alias_match === "dev_addr") labels.append(element("small", "", "Alias por DevAddr de sesión"));
  node.append(icon("radio"), labels); return node;
}
function devicesTable(devices, compact = false) {
  const rows = devices.map(item => {
    const row = element("tr"); cell(row, deviceIdentity(item));
    if (!compact) { cell(row, item.dev_addr, "mono"); cell(row, item.fport); cell(row, item.fcnt16); }
    cell(row, numeric(item.rssi, " dBm")); cell(row, numeric(item.lsnr, " dB"));
    if (!compact) { cell(row, item.datr); cell(row, numeric(item.freq, " MHz", 3)); }
    cell(row, dateText(item.received_at, true)); cell(row, badge(text(item.status), item.status)); return row;
  });
  return table(compact ? ["Nombre", "RSSI", "SNR", "Última recepción", "Cola"] : ["Nombre", "DevAddr", "FPort", "FCnt16", "RSSI", "SNR", "Data Rate", "Frecuencia", "Última recepción", "Cola"], rows, compact ? "recent-device-table" : "device-table", "Dispositivos observados");
}
function renderDevices(data) {
  const devices = Array.isArray(data.devices) ? data.devices : [];
  const noData = () => empty("Sin dispositivos observados", data.queue?.state === "OK" ? "No hay metadatos rxpk en la ventana consultada." : "La base de datos no está disponible.", "devices");
  $("recent-devices").replaceChildren(devices.length ? devicesTable(devices.slice(0, 5), true) : noData());
  $("devices-table").replaceChildren(devices.length ? devicesTable(devices) : noData());
  if (devices.length) $("devices-table").append(element("p", "table-note", "Datos de aplicación no disponibles · Payload cifrado · Hasta 64 rxpk por datagrama."));
}
function renderQueueTable(queue) {
  const rows = Array.isArray(queue.rows) ? queue.rows : [];
  const body = rows.map(item => {
    const tr = element("tr"); tr.tabIndex = 0; tr.dataset.packetId = String(item.id); tr.setAttribute("aria-selected", String(item.id === selectedPacketId));
    cell(tr, "#" + item.id, "mono"); cell(tr, text(item.original_time), "mono"); cell(tr, dateText(item.received_at, true)); cell(tr, badge(text(item.status), item.status)); cell(tr, item.attempts); cell(tr, dateText(item.last_attempt, true)); cell(tr, dateText(item.sent_at, true)); cell(tr, dateText(item.ack_at, true)); cell(tr, numeric(item.delay_seconds, " s")); cell(tr, item.gateway_eui, "mono");
    const select = () => { selectedPacketId = item.id; renderPacket(item); document.querySelectorAll(".queue-table tr[data-packet-id]").forEach(row => row.setAttribute("aria-selected", String(row.dataset.packetId === String(item.id)))); };
    tr.addEventListener("click", select); tr.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } }); return tr;
  });
  $("queue-table").replaceChildren(rows.length ? table(["ID", "Original Time · epoch", "Received At", "Estado", "Intentos", "Último intento", "Sent At", "ACK At", "Delay", "Gateway EUI"], body, "queue-table", "Registros de uplink") : empty(queue.state === "OK" ? "Cola sin registros" : "DB: NO DISPONIBLE", queue.state === "OK" ? "No hay uplinks en la muestra actual." : "Queue UNKNOWN · Pending y Sent NO DISPONIBLES.", "database"));
  if (selectedPacketId !== null) {
    const selected = rows.find(item => item.id === selectedPacketId);
    if (selected) renderPacket(selected); else { selectedPacketId = null; $("packet-title").textContent = "Flujo de un paquete"; $("packet-state").replaceWith(Object.assign(badge("Sin selección", "UNKNOWN"), {id: "packet-state"})); $("timeline").replaceChildren(empty("El registro seleccionado ya no está en la ventana consultada.")); }
  }
}
function renderPacket(item) {
  $("packet-title").textContent = "Paquete #" + item.id;
  $("packet-state").replaceWith(Object.assign(badge(text(item.status), item.status), {id: "packet-state"}));
  const stages = [["radio", "RF recibido", null, "Marca RF no disponible"], ["database", "Registro SQLite", item.created_at, "Hora de creación; no commit exacto"], ["arrow", "Fast Send", null, "Sin marca registrada"], ["queue", "Último intento", item.last_attempt, "Intentos acumulados: " + text(item.attempts)], ["cloud", "PUSH_ACK UDP", item.ack_at, "No acredita entrega de aplicación"], ["check", "Sent", item.sent_at, "Marca de confirmación"]];
  $("timeline").replaceChildren(...stages.map(([graphic, label, timestamp, detail]) => {
    const stage = element("div", "packet-stage"); stage.dataset.state = instant(timestamp) ? "OK" : "UNKNOWN";
    stage.append(icon(graphic), element("strong", "", label), element("small", "", dateText(timestamp, true)), element("small", "", detail)); return stage;
  }));
}
function eventsFromRows(rows) {
  const fields = [["received_at", "received", "radio", "Recepción local registrada"], ["created_at", "created", "database", "Registro creado en SQLite"], ["last_attempt", "attempt", "queue", "Último intento registrado"], ["ack_at", "ack", "cloud", "PUSH_ACK UDP registrado"], ["sent_at", "sent", "check", "Marca sent registrada"]];
  const events = [];
  rows.forEach(row => fields.forEach(([field, kind, graphic, title]) => {
    const date = instant(row[field]);
    if (date) events.push({id: row.id, kind, graphic, title, timestamp: row[field], millis: date.getTime(), attempts: row.attempts});
  }));
  return events.sort((a, b) => b.millis - a.millis || b.id - a.id);
}
function eventTimeline(events, compact) {
  if (!events.length) return empty("Sin eventos registrados", "Solo se muestran marcas presentes en SQLite.", "events");
  const list = element("ol", "event-timeline");
  events.forEach(item => {
    const node = element("li", "event"), tile = element("span", "event-icon"); tile.append(icon(item.graphic));
    const body = element("div", "event-body"), top = element("div", "event-top"), time = element("time", "", dateText(item.timestamp, !compact));
    time.dateTime = instant(item.timestamp).toISOString(); time.title = text(item.timestamp);
    top.append(element("strong", "", item.title), time);
    body.append(top, element("p", "", "Paquete #" + item.id + (item.kind === "attempt" ? " · Intentos: " + text(item.attempts) : item.kind === "created" ? " · Hora de creación; no commit exacto" : item.kind === "ack" ? " · Recepción UDP, no ACK de aplicación" : " · Marca persistida")));
    node.append(tile, body); list.append(node);
  });
  return list;
}
function renderEvents() {
  $("recent-events").replaceChildren(eventTimeline(currentEvents.slice(0, 5), true));
  const filtered = eventFilter === "all" ? currentEvents : currentEvents.filter(item => item.kind === eventFilter);
  $("events-list").replaceChildren(eventTimeline(filtered.slice(0, 100), false));
}
document.querySelectorAll("[data-event-filter]").forEach(button => button.addEventListener("click", () => {
  eventFilter = button.dataset.eventFilter;
  document.querySelectorAll("[data-event-filter]").forEach(item => { const active = item === button; item.classList.toggle("active", active); item.setAttribute("aria-pressed", String(active)); });
  renderEvents();
}));
function renderAlert(data, stale) {
  const banner = $("alert-banner"), net = state(data.internet?.state), queue = data.queue || {}, pending = queue.summary?.pending;
  banner.replaceChildren(); banner.hidden = true;
  if (!stale && previousInternet === "OFFLINE" && net === "ONLINE") recovered = true;
  if (!stale && net !== "UNKNOWN") previousInternet = net;
  if (net !== "ONLINE" || !(pending > 0)) recovered = false;
  let title = "", detail = "", status = "WARNING";
  if (stale) { title = "Sin conexión con el dashboard"; detail = "Se conservan las últimas muestras. Los estados actuales no están verificados."; }
  else if (net === "OFFLINE") { title = "Sin Internet · supervisión local disponible"; detail = queue.state === "OK" ? (pending > 0 ? count(pending) + " uplinks almacenados en SQLite pendientes de reenvío automático. La actividad actual de reenvío no está medida." : "Cola consultable. No hay paquetes pendientes registrados en esta muestra.") : "Estado de la cola UNKNOWN. No se puede confirmar almacenamiento local."; }
  else if (recovered && pending > 0) { title = "Conectividad recuperada"; detail = count(pending) + " paquetes pendientes para reenvío automático. Consulte intentos y ACK registrados."; status = "ONLINE"; }
  else if (queue.state !== "OK") { title = "Base de datos no disponible"; detail = "Queue UNKNOWN · Pending y Sent no disponibles. El dashboard continúa sin crear archivos."; }
  if (title) { const content = element("div"); content.append(element("strong", "", title), element("p", "", detail)); banner.append(icon(status === "ONLINE" ? "check" : "alert"), content); banner.dataset.state = status; banner.hidden = false; }
}
function render(data, stale = false) {
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Muestra incompatible");
  lastData = data;
  const health = stale ? "UNKNOWN" : state(data.health);
  $("health").replaceWith(Object.assign(badge("HEALTH: " + health, health), {id: "health"}));
  $("sample").textContent = data.sampled_at ? (stale ? "Última muestra: " : "Actualizado: ") + dateText(data.sampled_at) : "Esperando primera muestra";
  const time = instant(data.system?.time);
  $("system-time").textContent = time ? dateText(data.system.time) : "—";
  $("mobile-system-time").textContent = time ? dateText(data.system.time) + " · UTC−5" : "Hora no disponible";
  $("system-date").textContent = time ? time.toLocaleDateString("es-CO", {timeZone: "America/Bogota", day: "2-digit", month: "short", year: "numeric"}) : "Hora del sistema no disponible";
  renderUPS(data, stale); renderKpis(data, stale); renderFlow(data, stale); renderSystem(data, stale); renderQueueSummary(data.queue || {}); renderAlert(data, stale);
  const stamp = data.updated_at?.queue ?? JSON.stringify([data.queue, data.devices]);
  if (stamp !== queueStamp) { queueStamp = stamp; renderDevices(data); renderQueueTable(data.queue || {}); currentEvents = eventsFromRows(Array.isArray(data.queue?.rows) ? data.queue.rows : []); renderEvents(); }
}
const upsLabels = {UNKNOWN: "DESCONOCIDO", CRITICAL: "BATERÍA CRÍTICA", LOW: "BATERÍA BAJA", FAST_CHARGING: "CARGA RÁPIDA", CHARGING: "CARGANDO", DISCHARGING: "DESCARGANDO", IDLE: "EN ESPERA"};

let retry = 1000;
function connect() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/status");
  ws.onopen = () => { retry = 1000; $("connection").textContent = "Interfaz conectada"; $("connection").dataset.state = "ONLINE"; };
  ws.onmessage = event => {
    try { render(JSON.parse(event.data)); $("connection").textContent = "Interfaz conectada"; $("connection").dataset.state = "ONLINE"; }
    catch (error) { $("connection").textContent = "Muestra no disponible"; $("connection").dataset.state = "UNKNOWN"; }
  };
  ws.onclose = () => { $("connection").textContent = "Conexión interrumpida"; $("connection").dataset.state = "STALE"; if (lastData) render(lastData, true); setTimeout(connect, retry); retry = Math.min(30000, retry * 2); };
  ws.onerror = () => ws.close();
}
render({health: "UNKNOWN", queue: {state: "UNKNOWN", rows: []}, devices: [], services: [], internet: {state: "UNKNOWN"}});
goTo("overview");
connect();

// UPS availability follows transport state and the backend, without comparing clocks.
function upsValue(data, stale) {
  const ups = data.ups || {};
  return !stale && ups.state === "OK" ? ups : {state: "UNKNOWN", battery_state: "UNKNOWN", charge_state: "UNKNOWN"};
}
function upsVisual(ups) {
  const validCharge = ["FAST_CHARGING", "CHARGING", "DISCHARGING", "IDLE"].includes(ups.charge_state);
  const status = ups.state !== "OK" || ups.battery_state === "UNKNOWN" || !validCharge ? "UNKNOWN"
    : ups.battery_state === "CRITICAL" ? "CRITICAL" : ups.battery_state === "LOW" ? "LOW" : ups.charge_state;
  return {state: status, label: upsLabels[status], className: "ups-" + status.toLowerCase().replaceAll("_", "-")};
}
function upsKpi(ups) {
  const visual = upsVisual(ups);
  const charging = ["CHARGING", "FAST_CHARGING"].includes(ups.charge_state);
  const card = kpi("UPS", charging && visual.state !== "UNKNOWN" ? "battery-charging" : "battery", ups.state === "OK" ? numeric(ups.battery_percent, " %", 0) : "UNKNOWN", visual.label, ups.battery_state || "UNKNOWN");
  card.classList.add("ups-kpi", visual.className);
  return card;
}
function upsStatus(label, visual) {
  const node = badge(label, visual.state);
  node.classList.add("ups-status", visual.className);
  return node;
}
function renderUPS(data, stale) {
  const ups = upsValue(data, stale), known = ups.state === "OK", visual = upsVisual(ups);
  const panel = document.querySelector(".ups-panel");
  Object.keys(upsLabels).forEach(key => panel.classList.remove("ups-" + key.toLowerCase().replaceAll("_", "-")));
  panel.classList.add(visual.className);
  const power = ups.external_power === true ? "PRESENT" : ups.external_power === false ? "NOT_PRESENT" : "UNKNOWN";
  const overview = () => [["UPS · Batería", known ? numeric(ups.battery_percent, " %", 0) : "UNKNOWN"], ["Voltaje pack", numeric(ups.battery_voltage_mv / 1000, " V", 3)], ["Corriente", numeric(ups.battery_current_ma, " mA")], ["Estado de carga", upsStatus(upsLabels[ups.charge_state] || upsLabels.UNKNOWN, visual)], ["Alimentación externa", power], ["Desbalance de celdas", numeric(ups.cell_delta_mv, " mV", 0)]];
  $("ups-overview").replaceChildren(detailList(overview()));
  $("ups-cells").replaceChildren();
  $("ups-cell-summary").replaceChildren();
  if (!known) {
    $("ups-detail").replaceChildren(empty("UPS no disponible · DESCONOCIDO", "Sin lectura I²C válida en 0x2d · UNKNOWN", "battery"));
    return;
  }
  $("ups-detail").replaceChildren(detailList([
    ["Estado UPS", upsStatus(visual.label, visual)], ["Estado batería", badge(ups.battery_state)], ...overview(),
    ["Potencia batería · CALCULADA", numeric(ups.battery_power_mw, " mW")],
    ["Capacidad restante", numeric(ups.remaining_capacity_mah, " mAh", 0)],
    ["VBUS Voltage", numeric(ups.vbus_voltage_mv, " mV")], ["VBUS Current", numeric(ups.vbus_current_ma, " mA")], ["VBUS Power", numeric(ups.vbus_power_mw, " mW")],
    ["Estimación IC · valor instantáneo del fuel gauge", numeric(ups.runtime_to_empty_min, " min", 0)],
    ["Tiempo a carga completa · IC", numeric(ups.time_to_full_min, " min", 0)], ["Última muestra UPS", dateText(ups.sampled_at, true)]
  ]));
  (Array.isArray(ups.cells_mv) ? ups.cells_mv : []).forEach((mv, i) => {
    const cell = element("div", "ups-cell");
    cell.append(icon("battery"), element("strong", "", "C" + (i + 1)), element("span", "", numeric(mv / 1000, " V", 3)));
    $("ups-cells").append(cell);
  });
  $("ups-cell-summary").append(detailList([["Mínimo", numeric(ups.cell_min_mv, " mV", 0)], ["Máximo", numeric(ups.cell_max_mv, " mV", 0)], ["Delta", numeric(ups.cell_delta_mv, " mV", 0)], ["Balance · criterio visual del dashboard", badge(ups.cell_balance_state)]]));
}
