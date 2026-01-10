// Vetflow calendario (version simplificada)
(() => {
  const pageError = (msg) => {
    console.error(msg);
    const container = document.querySelector(".tab-content") || document.body;
    const alert = document.createElement("div");
    alert.className = "alert alert-danger mt-2";
    alert.textContent = `Error en calendario: ${msg}`;
    container.prepend(alert);
  };

  window.onerror = function (msg, src, line, col, err) {
    const normalized = String(msg || "").toLowerCase();
    if (normalized.includes("script error")) {
      console.warn("Ignored external script error", msg);
      return true;
    }
    pageError(msg);
    console.error("Calendar error", src, line, col, err);
  };

  console.log("calendar.js cargado");
  // Si la UI del calendario viejo ya no existe, evitamos intentar renderizarla.
  const hasLegacyCalendarSurface =
    !!document.getElementById("calendarGrid") || !!document.getElementById("timelineWrapper");
  // helpers expuestos
  const pad = (n) => String(n).padStart(2, "0");
  const getWorkspaceSlug = () => {
    const surface = document.getElementById('calendarSurface');
    return surface?.getAttribute('data-workspace-slug')?.trim() || '';
  };
  const getApiBase = () => {
    const slug = getWorkspaceSlug();
    return slug ? `/w/${encodeURIComponent(slug)}/api/calendar` : '/api/calendar';
  };

  const getClientsApiBase = () => {
    const slug = getWorkspaceSlug();
    return slug ? `/w/${encodeURIComponent(slug)}/api/clientes` : '';
  };

  let clientsCache = null;
  let clientsLoading = null;

  async function ensureClientsLoaded() {
    if (Array.isArray(clientsCache)) return clientsCache;
    if (clientsLoading) return clientsLoading;
    const base = getClientsApiBase();
    if (!base) {
      clientsCache = [];
      return clientsCache;
    }
    clientsLoading = (async () => {
      try {
        const res = await fetch(`${base}?limit=500`, { headers: { Accept: "application/json" } });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `Error ${res.status}`);
        clientsCache = Array.isArray(data.clients) ? data.clients : [];
        return clientsCache;
      } catch (err) {
        console.warn("No se pudieron cargar clientes:", err?.message || err);
        clientsCache = [];
        return clientsCache;
      } finally {
        clientsLoading = null;
      }
    })();
    return clientsLoading;
  }

  const formatClientLabel = (client) => {
    if (!client) return "";
    const name = String(client.full_name || "").trim() || `Cliente #${client.id}`;
    const idType = String(client.id_type || "").trim();
    const idNumber = String(client.id_number || "").trim();
    const idText = idNumber ? (idType ? `${idType}: ${idNumber}` : idNumber) : "";
    return idText ? `${name} (${idText})` : name;
  };

  function populateClientSelect(selectEl, selectedId, clients) {
    if (!selectEl) return;
    const list = Array.isArray(clients) ? clients : [];
    const selected = selectedId === null || selectedId === undefined || selectedId === "" ? "" : String(selectedId);

    selectEl.innerHTML = "";

    const noneOpt = document.createElement("option");
    noneOpt.value = "";
    noneOpt.textContent = "Sin cliente";
    selectEl.appendChild(noneOpt);

    let found = selected === "";
    for (const client of list) {
      const opt = document.createElement("option");
      opt.value = String(client.id);
      opt.textContent = formatClientLabel(client);
      if (opt.value === selected) {
        opt.selected = true;
        found = true;
      }
      selectEl.appendChild(opt);
    }

    if (!found && selected) {
      const opt = document.createElement("option");
      opt.value = selected;
      opt.textContent = `Cliente #${selected}`;
      opt.selected = true;
      selectEl.appendChild(opt);
      found = true;
    }

    selectEl.value = found ? selected : "";
  }
  const getWebBase = () => {
    const slug = getWorkspaceSlug();
    // Nota: Si hay slug, las rutas de la app web a veces no se prefijan con /w/slug si la app maneja la sesión
    // Pero para asegurarnos que el contexto se mantiene en POST/redirects puede ser útil.
    // Sin embargo, las rutas en routes/calendar.py para POST de borrar son /calendar/<id>/delete (global).
    // Vamos a intentar mantener la misma consistencia.
    return '';
  };

  const formatDateYMD = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const formatHourHM = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const toInput = (dateString) => {
    const d = new Date(dateString);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const formatLocalPayload = (value) => {
    // Enviar ISO con offset local para que el backend guarde el instante correcto en timestamptz
    const d = value instanceof Date ? value : new Date(value);
    if (isNaN(d.getTime())) return "";

    const offsetMinutes = -d.getTimezoneOffset();
    const sign = offsetMinutes >= 0 ? "+" : "-";
    const abs = Math.abs(offsetMinutes);
    const offH = pad(Math.floor(abs / 60));
    const offM = pad(abs % 60);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00${sign}${offH}:${offM}`;
  };
  window.formatLocalPayload = formatLocalPayload;
  const parseLocalDate = (v) => {
    if (!v) return null;
    const d = new Date(v);
    return isNaN(d.getTime()) ? null : d;
  };
  window.getSas = async (id) => {
    const res = await fetch(`/file/${id}/sas`);
    const data = await res.json();
    if (data.url) prompt("URL SAS (1h):", data.url);
    else alert(data.error || "Error generando URL");
  };
  window.openFile = async (id) => {
    const res = await fetch(`/file/${id}/sas`);
    const data = await res.json();
    if (data.url) window.open(data.url, "_blank");
    else alert(data.error || "No se pudo generar URL");
  };

  const DEFAULT_STATUS_OPTIONS = [
    { value: "programada", label: "Programada" },
    { value: "confirmada", label: "Confirmada" },
    { value: "completada", label: "Completada" },
    { value: "cancelada", label: "Cancelada" },
    { value: "no_show", label: "No asistio" },
  ];
  const STATUS_OPTIONS =
    Array.isArray(window.vetflowStatuses) && window.vetflowStatuses.length
      ? window.vetflowStatuses
      : DEFAULT_STATUS_OPTIONS;
  const STATUS_LABELS =
    (window.vetflowStatusLabels && Object.keys(window.vetflowStatusLabels).length
      ? window.vetflowStatusLabels
      : STATUS_OPTIONS.reduce((acc, opt) => {
        acc[opt.value] = opt.label;
        return acc;
      }, {})) || {};
  const DEFAULT_STATUS = STATUS_OPTIONS[0]?.value || "programada";
  const renderStatusOptions = (selectedValue) => {
    const selected = selectedValue || DEFAULT_STATUS;
    return STATUS_OPTIONS.map(
      (opt) => `<option value="${opt.value}" ${opt.value === selected ? "selected" : ""}>${opt.label}</option>`
    ).join("");
  };
  const renderStatusBadge = (statusValue) => {
    const value = statusValue || DEFAULT_STATUS;
    const label = STATUS_LABELS[value] || value;
    return `<span class="status-badge status-${value}">${label}</span>`;
  };
  const LOCKED_STATUS_VALUES = ["cancelada", "completada", "no_show"];
  const isStatusLocked = (status) => LOCKED_STATUS_VALUES.includes(String(status || "").toLowerCase());

  window.openEdit = (id, title, description, start, end, status = DEFAULT_STATUS, clientId = null) => {
    const formHtml = `
      <form method="post" action="/calendar/${id}/update" onsubmit="
        const s = this.querySelector('[name=ui_start]').value;
        const e = this.querySelector('[name=ui_end]').value;
        this.querySelector('[name=start_time]').value = window.formatLocalPayload(s);
        this.querySelector('[name=start_time]').value = window.formatLocalPayload(s);
        this.querySelector('[name=end_time]').value = window.formatLocalPayload(e);
        this.querySelector('[name=timezone]').value = Intl.DateTimeFormat().resolvedOptions().timeZone;
      ">
        <div class="mb-2"><label class="form-label">Titulo</label><input class="form-control" name="title" value="${title}"></div>
        <div class="mb-2"><label class="form-label">Descripcion</label><input class="form-control" name="description" value="${description || ""}"></div>
        <div class="mb-2">
          <label class="form-label">Cliente (opcional)</label>
          <select class="form-select" name="client_id" data-client-select></select>
        </div>
        
        <input type="hidden" name="start_time">
        <input type="hidden" name="start_time">
        <input type="hidden" name="start_time">
        <input type="hidden" name="end_time">
        <input type="hidden" name="timezone">
        <input type="hidden" name="timezone">
        
        <div class="mb-2"><label class="form-label">Inicio</label><input class="form-control" type="datetime-local" name="ui_start" value="${toInput(start)}" required></div>
        <div class="mb-2"><label class="form-label">Fin</label><input class="form-control" type="datetime-local" name="ui_end" value="${toInput(end)}" required></div>
        <div class="mb-2"><label class="form-label">Estado</label>
          <select class="form-select" name="status">
            ${renderStatusOptions(status)}
          </select>
        </div>
        <div class="text-end"><button class="btn btn-primary" type="submit">Guardar cambios</button></div>
      </form>`;
    const modalEl = document.createElement("div");
    modalEl.className = "modal fade";
    modalEl.innerHTML = `<div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Editar cita</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body">${formHtml}</div></div></div>`;
    document.body.appendChild(modalEl);
    const modal = new bootstrap.Modal(modalEl);
    modal.show();

    const clientSelect = modalEl.querySelector("[data-client-select]");
    populateClientSelect(clientSelect, clientId, clientsCache || []);
    if (!Array.isArray(clientsCache)) {
      if (clientSelect) clientSelect.disabled = true;
      void ensureClientsLoaded()
        .then((clients) => populateClientSelect(clientSelect, clientId, clients))
        .finally(() => {
          if (clientSelect) clientSelect.disabled = false;
        });
    }

    modalEl.addEventListener("hidden.bs.modal", () => modalEl.remove());
  };

  // miniaturas
  async function loadThumbnails() {
    const imgs = document.querySelectorAll("img[data-file-id][data-is-image='true']");
    for (const img of imgs) {
      const id = img.getAttribute("data-file-id");
      const status = (img.getAttribute("data-status") || "").toLowerCase();
      if (["expired", "expirada", "deleted", "eliminado"].includes(status)) {
        img.replaceWith(document.createTextNode("-"));
        continue;
      }
      try {
        const res = await fetch(`/file/${id}/sas`);
        const data = await res.json();
        if (data.url) img.src = data.url;
        else img.replaceWith(document.createTextNode("-"));
      } catch {
        img.replaceWith(document.createTextNode("-"));
      }
    }
  }

  // UI refs
  const calendarGrid = document.getElementById("calendarGrid");
  const calendarMonthLabel = document.getElementById("calendarMonthLabel");
  const calendarMonthMeta = document.getElementById("calendarMonthMeta");
  const prevMonthBtn = document.getElementById("prevMonth");
  const nextMonthBtn = document.getElementById("nextMonth");
  const todayBtn = document.getElementById("todayBtn");
  const viewButtons = document.querySelectorAll("[data-calendar-view]");
  const timelineWrapper = document.getElementById("timelineWrapper");
  const timelineHeader = document.getElementById("timelineHeader");
  const timelineBody = document.getElementById("timelineBody");
  const timelineScroll = document.getElementById("timelineScroll");
  const timelineLoading = document.getElementById("timelineLoading");
  const monthWeekdaysHeader = document.getElementById("monthWeekdaysHeader");
  const createEventModalEl = document.getElementById("createEventModal");
  const createEventForm = document.getElementById("createEventForm");
  const eventTitleInput = document.getElementById("eventTitleInput");
  const eventDescInput = document.getElementById("eventDescInput");
  const eventRangeLabel = document.getElementById("eventRangeLabel");
  const eventStartIso = document.getElementById("eventStartIso");
  const eventEndIso = document.getElementById("eventEndIso");
  const eventStartInput = document.getElementById("eventStartInput");
  const eventEndInput = document.getElementById("eventEndInput");
  const eventStatusSelect = document.getElementById("eventStatusSelect");
  const eventClientSelect = document.getElementById("eventClientSelect");
  const appointmentsTableBody = document.getElementById("appointmentsTableBody");
  const bulkDeleteBtn = document.getElementById("bulkDeleteBtn");
  const selectAllAppointments = document.getElementById("selectAllAppointments");
  const quickEventBtn = document.getElementById("openQuickEventBtn");
  const calendarMonthHero = document.getElementById("calendarMonthHero");
  let createEventModal;
  const setTimelineLoading = (state) => {
    if (!timelineLoading) return;
    timelineLoading.classList.toggle("d-none", !state);
  };

  const rememberTimelineScroll = () => {
    if (!timelineScroll || applyingTimelineScroll) return;
    savedTimelineScrollTop = timelineScroll.scrollTop;
    savedTimelineScrollLeft = timelineScroll.scrollLeft;
    timelineScrollWasUserSet = true;
  };
  timelineScroll?.addEventListener("scroll", rememberTimelineScroll);

  const initialAppointments = (window.vetflowData && window.vetflowData.appointments) || [];
  const events = (initialAppointments || []).map((ev) => ({
    ...ev,
    status: ev.status || DEFAULT_STATUS,
    start: parseLocalDate(ev.start_time),
    end: parseLocalDate(ev.end_time),
  }));

  const SLOT_MINUTES = 30;
  const ROW_HEIGHT = 32;
  const DAY_START_HOUR = 0;
  const DAY_END_HOUR = 24;
  const DEFAULT_SCROLL_HOUR = 6;
  const DAY_MS = 24 * 60 * 60 * 1000;
  let timelineMetrics = null;
  let dragState = null;
  let savedTimelineScrollTop = null;
  let savedTimelineScrollLeft = 0;
  let timelineScrollWasUserSet = false;
  let applyingTimelineScroll = false;
  let currentTimeIndicatorEl = null;
  let currentTimeTimer = null;
  let currentTimelineDays = [];

  let currentView = localStorage.getItem("calendar.view") || "week";
  let anchorDate = new Date(parseInt(localStorage.getItem("calendar.anchor") || Date.now(), 10));
  if (isNaN(anchorDate.getTime()) || anchorDate.getFullYear() < 2000) anchorDate = new Date();
  let selecting = false;
  let selectionStartTs = null;
  let lastHoverTs = null;
  let selectedSlots = [];
  let currentEventId = null;
  let currentEventSnapshot = null;
  const setMonthHero = (date) => {
    if (!calendarMonthHero) return;
    const opts = { month: "long", year: "numeric" };
    calendarMonthHero.textContent = date.toLocaleDateString("es-ES", opts);
  };

  const sameDate = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  const startOfWeekMonday = (date) => {
    const d = new Date(date);
    const day = d.getDay() === 0 ? 7 : d.getDay();
    d.setDate(d.getDate() - (day - 1));
    d.setHours(0, 0, 0, 0);
    return d;
  };
  const renderMonthWeekdays = () => {
    if (!monthWeekdaysHeader) return;
    const weekStart = startOfWeekMonday(anchorDate);
    monthWeekdaysHeader.innerHTML = "";
    for (let i = 0; i < 7; i++) {
      const d = new Date(weekStart);
      d.setDate(weekStart.getDate() + i);
      const col = document.createElement("div");
      const label = d.toLocaleDateString("es-ES", { weekday: "short" }).replace(".", "");
      col.textContent = label.toUpperCase();
      monthWeekdaysHeader.appendChild(col);
    }
  };
  const disableCurrentTimeIndicator = () => {
    if (currentTimeTimer) {
      clearInterval(currentTimeTimer);
      currentTimeTimer = null;
    }
    currentTimelineDays = [];
    if (currentTimeIndicatorEl) currentTimeIndicatorEl.classList.add("d-none");
  };
  const updateCurrentTimeIndicator = () => {
    if (!timelineBody || !timelineMetrics || !currentTimelineDays.length) return;

    // Ensure relative positioning for absolute child
    if (timelineBody.style.position !== "relative") timelineBody.style.position = "relative";

    const now = new Date();
    const dayIdx = currentTimelineDays.findIndex((d) => sameDate(d, now));

    if (dayIdx === -1) {
      currentTimeIndicatorEl?.remove();
      return;
    }

    const minutesFromStart = now.getHours() * 60 + now.getMinutes() - DAY_START_HOUR * 60;
    const totalMinutes = (DAY_END_HOUR - DAY_START_HOUR) * 60;

    if (minutesFromStart < 0 || minutesFromStart > totalMinutes) {
      currentTimeIndicatorEl?.remove();
      return;
    }

    const topPx = (minutesFromStart / SLOT_MINUTES) * ROW_HEIGHT;

    if (!currentTimeIndicatorEl || !document.contains(currentTimeIndicatorEl)) {
      if (currentTimeIndicatorEl) currentTimeIndicatorEl.remove();
      currentTimeIndicatorEl = document.createElement("div");
      currentTimeIndicatorEl.className = "current-time-indicator";
      currentTimeIndicatorEl.style.position = "absolute";
      currentTimeIndicatorEl.style.height = "2px";
      currentTimeIndicatorEl.style.backgroundColor = "#ea4335";
      currentTimeIndicatorEl.style.zIndex = "50";
      currentTimeIndicatorEl.style.pointerEvents = "none";

      const dot = document.createElement("span");
      dot.className = "current-time-dot";
      dot.style.position = "absolute";
      dot.style.width = "11px";
      dot.style.height = "11px";
      dot.style.backgroundColor = "#ea4335";
      dot.style.borderRadius = "50%";
      dot.style.top = "-4.5px"; // Centered relative to 2px line
      dot.style.left = "-5.5px"; // Centered on line start
      currentTimeIndicatorEl.appendChild(dot);
      timelineBody.appendChild(currentTimeIndicatorEl);
    }

    const dayPos = timelineMetrics.dayPositions?.[dayIdx];
    const columnWidth = dayPos?.width || timelineMetrics.dayWidth;
    const columnLeft = dayPos && typeof dayPos.left === "number"
      ? dayPos.left
      : timelineMetrics.hoursColWidth + dayIdx * columnWidth;

    currentTimeIndicatorEl.style.top = `${topPx}px`;
    currentTimeIndicatorEl.style.left = `${columnLeft}px`;
    currentTimeIndicatorEl.style.width = `${columnWidth}px`;
    currentTimeIndicatorEl.classList.remove("d-none");
    currentTimeIndicatorEl.style.display = "block";
  };
  const scheduleCurrentTimeIndicator = () => {
    if (currentTimeTimer) clearInterval(currentTimeTimer);
    updateCurrentTimeIndicator();
    currentTimeTimer = setInterval(updateCurrentTimeIndicator, 60000);
  };
  const formatRangeLabelText = (startDate, endDate) => {
    if (!startDate || !endDate) return "";
    const sameDayRange = sameDate(startDate, endDate);
    const dayOpts = { weekday: "short", day: "numeric", month: "short" };
    const startDay = startDate.toLocaleDateString("es-ES", dayOpts);
    const startHour = startDate.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
    const endDay = endDate.toLocaleDateString("es-ES", dayOpts);
    const endHour = endDate.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
    return sameDayRange ? `${startDay} ${startHour} - ${endHour}` : `${startDay} ${startHour} -> ${endDay} ${endHour}`;
  };
  function updateRangeLabelFromInputs() {
    if (!eventRangeLabel) return;
    const startVal = eventStartInput?.value;
    const endVal = eventEndInput?.value;
    // parseLocalDate maneja "yyyy-MM-ddThh:mm"
    const startDate = parseLocalDate(startVal);
    const endDate = parseLocalDate(endVal);
    if (!startDate || !endDate) {
      eventRangeLabel.textContent = "";
      return;
    }
    eventRangeLabel.textContent = formatRangeLabelText(startDate, endDate);
  }

  function primeCreateModalRange(startDate, endDate) {
    if (!startDate || !endDate) return;
    // Inputs `datetime-local` requieren formato local (YYYY-MM-DDTHH:MM)
    const startLocal = toInput(startDate);
    const endLocal = toInput(endDate);

    if (eventStartInput) eventStartInput.value = startLocal;
    if (eventEndInput) eventEndInput.value = endLocal;

    // Mantener hidden ISO (con offset) para integraciones si existen
    if (eventStartIso) eventStartIso.value = formatLocalPayload(startDate);
    if (eventEndIso) eventEndIso.value = formatLocalPayload(endDate);

    // Actualizamos el label visual
    updateRangeLabelFromInputs();
  }

  const handleCreateInputChange = () => {
    // Sincronizar hidden ISO (con offset) a partir del valor local seleccionado
    if (eventStartInput && eventStartIso) {
      const d = parseLocalDate(eventStartInput.value);
      eventStartIso.value = d ? formatLocalPayload(d) : eventStartInput.value;
    }
    if (eventEndInput && eventEndIso) {
      const d = parseLocalDate(eventEndInput.value);
      eventEndIso.value = d ? formatLocalPayload(d) : eventEndInput.value;
    }

    updateRangeLabelFromInputs();
  };
  eventStartInput?.addEventListener("input", handleCreateInputChange);
  eventEndInput?.addEventListener("input", handleCreateInputChange);
  updateRangeLabelFromInputs();
  const getRoundedDefaultRange = () => {
    const start = new Date();
    start.setSeconds(0, 0);
    const remainder = start.getMinutes() % SLOT_MINUTES;
    if (remainder !== 0) start.setMinutes(start.getMinutes() + (SLOT_MINUTES - remainder));
    const end = new Date(start.getTime() + SLOT_MINUTES * 2 * 60000);
    return { start, end };
  };

  function setView(view) {
    if (!hasLegacyCalendarSurface) return;
    currentView = view;
    viewButtons.forEach((btn) => btn.classList.toggle("active", btn.dataset.calendarView === view));
    localStorage.setItem("calendar.view", view);
    renderCalendar();
  }
  function shiftPeriod(delta) {
    if (!hasLegacyCalendarSurface) return;
    if (currentView === "month") anchorDate = new Date(anchorDate.getFullYear(), anchorDate.getMonth() + delta, 1);
    else if (currentView === "week") anchorDate = new Date(anchorDate.getFullYear(), anchorDate.getMonth(), anchorDate.getDate() + delta * 7);
    else anchorDate = new Date(anchorDate.getFullYear(), anchorDate.getMonth(), anchorDate.getDate() + delta);
    localStorage.setItem("calendar.anchor", String(anchorDate.getTime()));
    renderCalendar();
  }

  function renderMonth() {
    console.log("renderMonth");
    disableCurrentTimeIndicator();
    if (!calendarGrid) return;
    calendarGrid.classList.remove("d-none");
    if (timelineWrapper) timelineWrapper.classList.add("d-none");
    if (monthWeekdaysHeader) {
      monthWeekdaysHeader.style.display = "";
      renderMonthWeekdays();
    }

    const monthStart = new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1);
    const start = startOfWeekMonday(monthStart);
    calendarGrid.innerHTML = "";
    const monthLabel = monthStart.toLocaleDateString("es-ES", { month: "long", year: "numeric" });
    calendarMonthLabel.textContent = monthLabel.charAt(0).toUpperCase() + monthLabel.slice(1);
    calendarMonthMeta.textContent = `Mes ${pad(monthStart.getMonth() + 1)} / Anio ${monthStart.getFullYear()}`;
    setMonthHero(monthStart);

    for (let i = 0; i < 42; i++) {
      const day = new Date(start);
      day.setDate(start.getDate() + i);
      const dayEvents = events.filter((ev) => ev.start && sameDate(ev.start, day));
      const cell = document.createElement("div");
      cell.className = "calendar-cell p-2";
      if (day.getMonth() !== monthStart.getMonth()) cell.classList.add("outside-month");
      if (sameDate(day, new Date())) cell.classList.add("border-primary");
      const header = document.createElement("div");
      header.className = "d-flex justify-content-between align-items-center";
      const dayNumber = document.createElement("span");
      dayNumber.className = "calendar-day";
      dayNumber.textContent = day.getDate();
      header.appendChild(dayNumber);
      cell.appendChild(header);
      dayEvents.slice(0, 3).forEach((ev) => {
        const pill = document.createElement("span");
        pill.className = "event-pill";
        const statusClass = ev.status ? `status-${String(ev.status).toLowerCase()}` : "";
        if (statusClass) pill.classList.add(statusClass);
        pill.textContent = `${ev.start.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}-${ev.end.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })} ${ev.title}`;
        cell.appendChild(pill);
      });
      cell.addEventListener("dblclick", () => {
        anchorDate = new Date(day);
        setView("day");
      });
      calendarGrid.appendChild(cell);
    }
  }

  function renderTimeline(view) {
    console.log("renderTimeline", view);
    if (!timelineWrapper || !timelineHeader || !timelineBody) return;
    setTimelineLoading(true);
    if (calendarGrid) calendarGrid.classList.add("d-none");
    timelineWrapper.classList.remove("d-none");
    if (monthWeekdaysHeader) monthWeekdaysHeader.style.display = "none";

    // Dynamic hours column width
    const isMobile = window.innerWidth < 768;
    const hoursColWidth = isMobile ? 50 : 80;

    const days = [];
    if (view === "week") {
      const start = startOfWeekMonday(anchorDate);
      for (let i = 0; i < 7; i++) {
        const d = new Date(start);
        d.setDate(start.getDate() + i);
        days.push(d);
      }
    } else {
      days.push(new Date(anchorDate));
    }
    timelineBody.classList.toggle("single-day", days.length === 1);

    const totalSlots = ((DAY_END_HOUR - DAY_START_HOUR) * 60) / SLOT_MINUTES;

    // Asegurar estructura del header (igual que en renderTimelineEvents)
    // --- LAYOUT TABLA UNIFICADA ---
    // Limpiar contenedores
    timelineHeader.innerHTML = "";
    timelineHeader.style.display = "none";
    timelineBody.innerHTML = "";
    timelineBody.style.display = "block";
    timelineBody.style.width = "100%";
    timelineBody.style.padding = "0";

    // Crear elementos de la tabla
    const table = document.createElement("table");
    table.style.width = "100%";
    table.style.borderCollapse = "separate";
    table.style.borderSpacing = "0";
    table.style.tableLayout = "fixed";

    const colgroup = document.createElement("colgroup");
    const colHour = document.createElement("col");
    colHour.style.width = `${hoursColWidth}px`;
    colgroup.appendChild(colHour);
    days.forEach(() => {
      const colDay = document.createElement("col");
      colgroup.appendChild(colDay);
    });
    table.appendChild(colgroup);

    // THEAD
    const thead = document.createElement("thead");
    const trHead = document.createElement("tr");

    const thEmpty = document.createElement("th");
    thEmpty.style.background = "#fff";
    thEmpty.style.position = "sticky";
    thEmpty.style.top = "0";
    thEmpty.style.zIndex = "20";
    thEmpty.style.borderBottom = "1px solid #e3e8ee";
    trHead.appendChild(thEmpty);

    const today = new Date();
    days.forEach(d => {
      const th = document.createElement("th");
      th.className = "text-center py-2 border-start";
      th.style.background = "#fff";
      th.style.position = "sticky";
      th.style.top = "0";
      th.style.zIndex = "20";
      th.style.borderBottom = "1px solid #e3e8ee";

      const weekday = d.toLocaleDateString("es-ES", { weekday: "short" }).replace(".", "");
      const monthLabel = d.toLocaleDateString("es-ES", { month: "short" });
      const isToday = sameDate(d, today);

      th.innerHTML = `
            <div class="timeline-day" style="display:flex; flex-direction:column; align-items:center;">
                <div class="timeline-day-label" style="font-size:0.75rem; color:#7b6ae4; text-transform:uppercase;">${weekday}</div>
                <div class="timeline-day-number${isToday ? " is-today" : ""}" style="font-size:1.1rem; font-weight:700;">${d.getDate()}</div>
                <div class="timeline-day-month" style="font-size:0.7rem; color:#999;">${monthLabel}</div>
            </div>
        `;
      trHead.appendChild(th);
    });
    thead.appendChild(trHead);
    table.appendChild(thead);

    // TBODY
    const tbody = document.createElement("tbody");
    const docFrag = document.createDocumentFragment();
    const slotTdMap = new Map();
    days.forEach((_, idx) => slotTdMap.set(idx, []));

    for (let slot = 0; slot < totalSlots; slot++) {
      const minutesFromStart = DAY_START_HOUR * 60 + slot * SLOT_MINUTES;
      const tr = document.createElement("tr");
      tr.style.height = `${ROW_HEIGHT}px`;

      // Celda Hora
      const tdHour = document.createElement("td");
      tdHour.className = "timeline-hour text-end pe-2";
      tdHour.style.verticalAlign = "top";
      tdHour.style.borderBottom = "1px solid #f0f0f0";
      tdHour.style.fontSize = "0.75rem";
      tdHour.style.color = "#9ca3af";
      tdHour.style.background = "#fff";

      if (slot % 2 === 0) {
        tdHour.textContent = `${pad(Math.floor(minutesFromStart / 60))}:${pad(minutesFromStart % 60)}`;
        tdHour.style.transform = "translateY(-50%)";
      }
      tr.appendChild(tdHour);

      // Celdas Días
      days.forEach((d, dayIdx) => {
        const td = document.createElement("td");
        td.className = "time-slot";
        td.style.borderBottom = "1px solid #f0f0f0";
        td.style.borderLeft = "1px solid #f8f9fa";
        td.style.padding = "0";
        td.style.position = "relative";
        if (slot % 2 !== 0) td.style.backgroundColor = "rgba(249, 250, 251, 0.4)";

        const slotStart = new Date(d);
        slotStart.setHours(0, minutesFromStart, 0, 0);
        const slotEnd = new Date(slotStart);
        slotEnd.setMinutes(slotEnd.getMinutes() + SLOT_MINUTES);

        td.dataset.start = slotStart.toISOString();
        td.dataset.end = slotEnd.toISOString();
        td.dataset.slotKey = `${dayIdx}-${slot}`;

        td.addEventListener("mousedown", handleSlotDown);
        td.addEventListener("mouseenter", handleSlotEnter);
        td.addEventListener("mouseup", handleSlotUp);

        slotTdMap.get(dayIdx).push(td);
        tr.appendChild(td);
      });
      docFrag.appendChild(tr);
    }
    tbody.appendChild(docFrag);
    table.appendChild(tbody);
    timelineBody.appendChild(table);

    // Labels de Mes/Año
    calendarMonthLabel.textContent =
      view === "week"
        ? `${days[0].toLocaleDateString("es-ES", { day: "numeric", month: "short" })} - ${days[days.length - 1].toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric" })}`
        : days[0].toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    calendarMonthMeta.textContent = view === "week" ? "Vista semanal" : "Vista diaria";
    setMonthHero(days[0]);

    // Renderizado Eventos
    // Pasamos el slotTdMap para saber dónde inyectar los eventos (o usamos coordenadas)
    // En este enfoque híbrido, para eventos que cruzan slots, lo mejor es un contenedor overlay, 
    // pero para simplicidad y alineación, pondremos el evento en el TD de inicio y le daremos height > 100%.
    // PROBLEMA: z-index y overflow de celda.
    // MEJOR: Un contenedor overlay absoluto sobre el tbody? Muy complejo de alinear.
    // SOLUCION: Usar el timelineBody como wrapper relativo y renderizar eventos con coordenadas absolutas Píxel
    // BASADAS en las posiciones de las columnas de la tabla.

    // Callback para recalcular posiciones de eventos cuando cambia el layout (resize/sidebar)
    const updateEventsLayout = () => {
      if (!tbody.rows.length) return;
      const colWidths = [];
      const firstRowCells = tbody.rows[0].cells;
      for (let i = 1; i < firstRowCells.length; i++) {
        const cell = firstRowCells[i];
        colWidths.push({
          left: cell.offsetLeft,
          width: cell.offsetWidth
        });
      }
      renderEventsOverlay(days, events, colWidths, timelineBody);
    };

    // Observer para mantener alineación si cambia el tamaño de la tabla
    if (timelineBody._resizeObserver) timelineBody._resizeObserver.disconnect();
    const ro = new ResizeObserver(() => {
      window.requestAnimationFrame(updateEventsLayout);
    });
    ro.observe(timelineBody);
    timelineBody._resizeObserver = ro;

    // Render inicial
    requestAnimationFrame(() => {
      updateEventsLayout();
      // Scroll inicial
      const defaultRows = Math.max(0, ((DEFAULT_SCROLL_HOUR - DAY_START_HOUR) * 60) / SLOT_MINUTES);
      timelineScroll.scrollTop = defaultRows * ROW_HEIGHT;
      setTimelineLoading(false);
    });
  }

  // Nueva función especializada para renderizar eventos usando "DOM Snapping"
  function renderEventsOverlay(days, events, colMetrics, container) {
    // Limpiar eventos previos
    container.querySelectorAll(".event-block").forEach(e => e.remove());
    const tbody = container.querySelector("tbody");
    if (!tbody) return;

    const containerRect = container.getBoundingClientRect();
    const rows = Array.from(tbody.rows);
    if (rows.length === 0) return;

    // HPER-PRECISION: Mapear timestamps a filas/celdas es complejo si solo calculamos.
    // Mejor: encontrar la fila base para cada hora.

    const segments = [];
    events.forEach((ev) => {
      if (!ev.start || !ev.end) return;
      const evStart = new Date(ev.start);
      const evEnd = new Date(ev.end);

      days.forEach((day, dayIdx) => {
        // Lógica de intersección de día...
        const dayStart = new Date(day);
        dayStart.setHours(0, 0, 0, 0);
        const dayEnd = new Date(dayStart);
        dayEnd.setHours(24, 0, 0, 0);

        if (evEnd <= dayStart || evStart >= dayEnd) return;

        // Clamping
        const startActual = new Date(Math.max(evStart.getTime(), dayStart.getTime()));
        const endActual = new Date(Math.min(evEnd.getTime(), dayEnd.getTime()));

        segments.push({ ev, start: startActual, end: endActual, dayIdx });
      });
    });

    // Agrupamiento para columnas (solapamiento)
    const grouped = new Map();
    segments.forEach(s => {
      const l = grouped.get(s.dayIdx) || [];
      l.push(s);
      grouped.set(s.dayIdx, l);
    });

    grouped.forEach((list, dayIdx) => {
      // Algoritmo de columnas...
      list.sort((a, b) => a.start - b.start || b.end - a.end);
      const active = [];
      let maxCols = 0;
      list.forEach((item) => {
        for (let i = active.length - 1; i >= 0; i--) if (active[i].end <= item.start) active.splice(i, 1);
        const used = new Set(active.map((a) => a.col));
        let col = 0;
        while (used.has(col)) col += 1;
        item.col = col;
        active.push({ col, end: item.end });
        maxCols = Math.max(maxCols, active.length);
      });

      const gutter = 2; // Espacio visual entre eventos

      list.forEach(item => {
        // 1. Calcular Slot Index basado en hora
        const dayRef = new Date(days[dayIdx]);
        dayRef.setHours(DAY_START_HOUR, 0, 0, 0);

        // Minutos desde el inicio del grid
        const minFromGrid = (item.start - dayRef) / 60000;
        const minDuration = (item.end - item.start) / 60000;

        // Slot index aproximado
        const slotIndex = Math.floor(minFromGrid / SLOT_MINUTES); // e.g. 17:30 -> (17.5*60 - 8*60)/30 = 19
        const slotFraction = (minFromGrid % SLOT_MINUTES) / SLOT_MINUTES; // % de offset dentro del slot

        // Validar rango filas
        if (slotIndex < 0 || slotIndex >= rows.length) return; // Fuera de rango horario visual

        // SNAPPING: Obtener celda real del DOM
        // Cells layout: [0]=Hour, [1]=Day0, [2]=Day1... por tanto dayIdx visual debe sumar 1?
        // Si days.length son las columnas de dias.
        // Mapa: dayIdx 0 en el array `days` -> column index 1 en la tabla (la 0 es hora).
        const cellIndex = dayIdx + 1;

        const row = rows[slotIndex];
        // Si el row existe...
        if (!row) return;

        const cell = row.cells[cellIndex];
        if (!cell) return;

        const cellRect = cell.getBoundingClientRect();
        // Coordenadas relativas al container
        const relativeTop = cellRect.top - containerRect.top + container.scrollTop; // + scrollTop si el container es el scroller?
        // OJO: container es timelineBody. timelineScroll es el padre scroller.
        // Si timelineBody es relative y no scrollea, relativeTop = cellRect.top - containerRect.top.
        // Si el sticky header empuja... getBoundingClientRect ya lo incluye.
        // SIMPLIFICACION: relativeTop = cellRect.top - containerRect.top.

        const baseTop = (cellRect.top - containerRect.top);
        const cellHeight = cellRect.height;

        const finalTop = baseTop + (cellHeight * slotFraction);

        // Altura total: calcular pixel a pixel o proporcional?
        // Proporcional al 'height' real de las filas (que puede variar 1px por borders)
        // Mejor: height = duration / SLOT * cellHeight_avg. O simplemente duration visual.
        const finalHeight = (minDuration / SLOT_MINUTES) * cellHeight;

        // Ancho y Left
        const cellWidth = cellRect.width;
        const cellLeft = cellRect.left - containerRect.left;

        // Padding interno celda
        const pad = 1;
        const availW = cellWidth - (pad * 2);
        const colW = (availW - (gutter * maxCols)) / (maxCols + 1);

        const finalLeft = cellLeft + pad + (item.col * (colW + gutter));

        // Render
        const block = document.createElement("div");
        block.className = "event-block";
        const statusValue = item.ev.status || DEFAULT_STATUS;
        const lockedStatus = isStatusLocked(statusValue);
        block.classList.add(`event-status-${statusValue}`);
        block.style.position = "absolute";
        block.style.top = `${finalTop}px`;
        block.style.left = `${finalLeft}px`;
        block.style.width = `${Math.max(10, colW)}px`;
        block.style.height = `${Math.max(finalHeight - 1, 15)}px`;

        const startHour = item.start.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
        const endHour = item.end.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });

        block.innerHTML = `
                <div class="event-block-time" style="font-size:10px; line-height:1;">${startHour} - ${endHour}</div>
                <div class="text-truncate fw-bold" style="font-size:11px; line-height:1.2;">${(item.ev.title || "").replace(/</g, "&lt;")}</div>
             `;

        // Event Handling (Click, Drag logic wrappers...)
        block.dataset.skipClick = "0";
        block.addEventListener("click", () => {
          if (block.dataset.skipClick === "1") { block.dataset.skipClick = "0"; return; }
          openEventModal(item);
        });

        if (!lockedStatus) {
          block.ondragstart = () => false; // Prevent native drag
          block.addEventListener("pointerdown", (ev) => startEventInteraction(ev, item, "move"));
          // Handles...
          const topHandle = document.createElement("div");
          topHandle.className = "event-handle event-handle-top";
          topHandle.addEventListener("pointerdown", (ev) => startEventInteraction(ev, item, "resize-start"));
          block.appendChild(topHandle);
          const bottomHandle = document.createElement("div");
          bottomHandle.className = "event-handle event-handle-bottom";
          bottomHandle.addEventListener("pointerdown", (ev) => startEventInteraction(ev, item, "resize-end"));
          block.appendChild(bottomHandle);
        } else {
          block.classList.add("event-block--locked");
        }

        container.appendChild(block);
      });
    });

    scheduleCurrentTimeIndicator();
  }

  function renderTimelineEvents(days, slotMap) {
    const isMobile = window.innerWidth < 768;

    // Fluid grid; calculamos ancho real de cada día después del layout
    // Usamos min-width en CSS para forzar scroll si es muy estrecho, pero dejamos que 1fr llene el espacio disponible
    const minColWidth = days.length === 1 ? 200 : 100; // Un poco mas tolerante
    const gridTemplate = `${hoursColWidth}px repeat(${days.length}, minmax(${minColWidth}px, 1fr))`;

    // Configurar header con contenedor interno para alinear con el body (sin scrollbar)
    if (timelineHeader) {
      if (!timelineHeader.querySelector(".timeline-header-grid")) {
        timelineHeader.innerHTML = "";
        const gridEl = document.createElement("div");
        gridEl.className = "timeline-header-grid";
        gridEl.style.display = "grid";
        timelineHeader.appendChild(gridEl);
      }

      const headerGrid = timelineHeader.querySelector(".timeline-header-grid");
      headerGrid.style.gridTemplateColumns = gridTemplate;

      // Ajustar contenedores
      if (timelineWrapper) timelineWrapper.style.width = "100%"; // Volvemos a 100% para que ocupe todo el ancho disponible
      if (timelineScroll) timelineScroll.style.width = "100%";

      // Sincronizar ancho del grid del header con el ancho del CONTENIDO del body
      const syncHeaderWidth = () => {
        if (timelineScroll && headerGrid) {
          // Si hay scroll horizontal (scrollWidth > clientWidth), el header debe medir lo mismo que el contenido (scrollWidth)
          // Si no hay scroll, debe medir lo mismo que el area visible (clientWidth)
          // timelineScroll es el elemento que hace scroll
          const targetWidth = timelineScroll.scrollWidth > timelineScroll.clientWidth
            ? timelineScroll.scrollWidth
            : timelineScroll.clientWidth;

          headerGrid.style.width = `${targetWidth}px`;
        }
      };

      // Observer
      if (!timelineHeader._resizeObserver) {
        const ro = new ResizeObserver(syncHeaderWidth);
        if (timelineScroll) ro.observe(timelineScroll);
        timelineHeader._resizeObserver = ro;
      }
      requestAnimationFrame(syncHeaderWidth);
    }

    if (timelineBody) {
      timelineBody.style.gridTemplateColumns = gridTemplate;
      timelineBody.style.width = "100%"; // Ocupa todo el ancho que el grid defina (lo cual puede forzar scroll en el padre)
      timelineBody.style.paddingRight = "0px";
      timelineBody.style.backgroundSize = "";
    }

    // Update global state for indicator
    currentTimelineDays = days.map((d) => new Date(d));

    if (timelineBody) timelineBody.querySelectorAll(".event-block").forEach((el) => el.remove());

    const computeBaseMetrics = () => {
      if (!timelineBody || !days.length) return null;
      const containerWidth = timelineBody.clientWidth || timelineBody.getBoundingClientRect().width;
      const usable = Math.max(0, containerWidth - hoursColWidth);
      const dayWidth = days.length === 1 ? Math.max(280, usable) : Math.max(120, usable / days.length);
      const positions = Array.from({ length: days.length }, (_, idx) => ({
        left: hoursColWidth + idx * dayWidth,
        width: dayWidth,
      }));
      return { positions, hoursWidth: hoursColWidth, dayWidth };
    };

    const measured = computeBaseMetrics();
    timelineMetrics = {
      hoursColWidth: measured?.hoursWidth || hoursColWidth,
      dayWidth: measured?.dayWidth || hoursColWidth,
      dayCount: days.length,
      dayDates: days,
      rowHeight: ROW_HEIGHT,
      slotMinutes: SLOT_MINUTES,
      gutter: 6,
      dayPositions: measured?.positions || [],
    };
    if (timelineBody && measured?.dayWidth) {
      timelineBody.style.backgroundSize = `100% ${ROW_HEIGHT}px, ${Math.max(measured.dayWidth, 80)}px 100%`;
    }

    const segments = [];
    events.forEach((ev) => {
      if (!ev.start || !ev.end) return;
      const evStart = new Date(ev.start);
      const evEnd = new Date(ev.end);
      days.forEach((day, idx) => {
        const dayStart = new Date(day);
        dayStart.setHours(0, 0, 0, 0);
        const dayEnd = new Date(dayStart);
        dayEnd.setHours(24, 0, 0, 0);
        if (evEnd <= dayStart || evStart >= dayEnd) return;
        const startClamped = new Date(Math.max(evStart.getTime(), dayStart.getTime()));
        const endClamped = new Date(Math.min(evEnd.getTime(), dayEnd.getTime()));
        segments.push({ ev, start: startClamped, end: endClamped, dayIdx: idx });
      });
    });

    const grouped = new Map();
    segments.forEach((seg) => {
      const list = grouped.get(seg.dayIdx) || [];
      list.push(seg);
      grouped.set(seg.dayIdx, list);
    });

    grouped.forEach((list, idx) => {
      list.sort((a, b) => a.start - b.start || a.end - b.end);
      const active = [];
      let maxCols = 0;
      list.forEach((item) => {
        for (let i = active.length - 1; i >= 0; i--) if (active[i].end <= item.start) active.splice(i, 1);
        const used = new Set(active.map((a) => a.col));
        let col = 0;
        while (used.has(col)) col += 1;
        item.col = col;
        active.push({ col, end: item.end });
        maxCols = Math.max(maxCols, active.length);
      });
      const gutter = timelineMetrics.gutter;
      const dayWidthLocal = (timelineMetrics.dayPositions[idx]?.width) || timelineMetrics.dayWidth;
      const widthPerCol = maxCols > 0 ? Math.max(40, (dayWidthLocal - gutter * (maxCols + 1)) / maxCols) : dayWidthLocal;

      list.forEach((item) => {
        if (!timelineBody) return;
        const dayStart = new Date(days[idx]);
        dayStart.setHours(0, 0, 0, 0);
        const dayEnd = new Date(dayStart);
        dayEnd.setHours(24, 0, 0, 0);
        const minutesFromStart = Math.max(0, (item.start.getTime() - dayStart.getTime()) / 60000);
        const durationMinutes = Math.max((item.end - item.start) / 60000, SLOT_MINUTES);
        const topPx = (minutesFromStart / SLOT_MINUTES) * ROW_HEIGHT;
        const heightPx = (durationMinutes / SLOT_MINUTES) * ROW_HEIGHT;
        const dayPos = timelineMetrics.dayPositions[idx];
        const dayLeft = dayPos ? dayPos.left : timelineMetrics.hoursColWidth + idx * dayWidthLocal;
        const baseLeft = dayLeft + gutter;
        const leftPx = baseLeft + item.col * (widthPerCol + gutter);
        const widthPx = Math.max(0, widthPerCol);
        const block = document.createElement("div");
        block.className = "event-block";
        const statusValue = item.ev.status || DEFAULT_STATUS;
        const lockedStatus = isStatusLocked(statusValue);
        block.classList.add(`event-status-${statusValue}`);
        block.style.top = `${topPx + 2}px`;
        block.style.left = `${leftPx}px`;
        block.style.width = `${widthPx}px`;
        block.style.height = `${Math.max(heightPx - 4, 36)}px`;
        const startHour = item.start.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
        const endHour = item.end.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
        block.innerHTML = `<div class="event-block-time">${startHour}-${endHour}</div><div class="event-block-title">${(item.ev.title || "").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>`;
        block.dataset.skipClick = "0";
        block.addEventListener("click", () => {
          if (block.dataset.skipClick === "1") {
            block.dataset.skipClick = "0";
            return;
          }
          openEventModal(item);
        });
        const evStart = item.ev.start instanceof Date ? item.ev.start : new Date(item.ev.start);
        const evEnd = item.ev.end instanceof Date ? item.ev.end : new Date(item.ev.end);
        const spansMultipleDays = !sameDate(evStart, evEnd);
        const durationMs = evEnd - evStart;
        const isMultiDay = spansMultipleDays && durationMs >= DAY_MS;
        if (!isMultiDay) {
          block.dataset.eventId = `${item.ev.id}`;
          block.dataset.dayIdx = String(idx);
          block.dataset.col = String(item.col ?? 0);
          block.dataset.width = String(widthPx);
          block.dataset.left = String(leftPx);
          block.dataset.top = String(topPx + 2);
          block.dataset.height = String(Math.max(heightPx - 4, 36));
          block.dataset.status = statusValue;
          if (!lockedStatus) {
            block.addEventListener("pointerdown", (ev) => startEventInteraction(ev, item, "move"));
            const topHandle = document.createElement("div");
            topHandle.className = "event-handle event-handle-top";
            topHandle.addEventListener("pointerdown", (ev) => startEventInteraction(ev, item, "resize-start"));
            const bottomHandle = document.createElement("div");
            bottomHandle.className = "event-handle event-handle-bottom";
            bottomHandle.addEventListener("pointerdown", (ev) => startEventInteraction(ev, item, "resize-end"));
            block.appendChild(topHandle);
            block.appendChild(bottomHandle);
          } else {
            block.classList.add("event-block--locked");
          }
        }
        timelineBody.appendChild(block);
      });
    });

    const defaultRows = Math.max(0, ((DEFAULT_SCROLL_HOUR - DAY_START_HOUR) * 60) / SLOT_MINUTES);
    const defaultTop = defaultRows * ROW_HEIGHT;
    const targetTop =
      timelineScrollWasUserSet && savedTimelineScrollTop !== null ? savedTimelineScrollTop : defaultTop;
    const targetLeft = timelineScrollWasUserSet ? savedTimelineScrollLeft || 0 : 0;
    timelineScroll.scrollTop = targetTop;
    timelineScroll.scrollLeft = targetLeft;
    savedTimelineScrollTop = targetTop;
    savedTimelineScrollLeft = targetLeft;
    applyingTimelineScroll = false;

    // Schedule indicator now that metrics are ready
    scheduleCurrentTimeIndicator();

    // Recalculo rapido tras layout
    const remeasure = () => {
      const m = computeBaseMetrics();
      if (!m) return;
      timelineMetrics.hoursColWidth = m.hoursWidth || timelineMetrics.hoursColWidth;
      timelineMetrics.dayWidth = m.dayWidth || timelineMetrics.dayWidth;
      timelineMetrics.dayPositions = m.positions || timelineMetrics.dayPositions;
      if (timelineBody && m.dayWidth) {
        timelineBody.style.backgroundSize = `100% ${ROW_HEIGHT}px, ${Math.max(m.dayWidth, 80)}px 100%`;
      }
      updateCurrentTimeIndicator();
      setTimelineLoading(false);
    };
    requestAnimationFrame(remeasure);
    setTimeout(remeasure, 80);
    setTimeout(remeasure, 160);
  }

  function startEventInteraction(ev, segment, mode) {
    if (!segment || !segment.ev || !timelineMetrics) return;
    if (isStatusLocked(segment.ev.status)) return;
    if (mode !== "move") ev.preventDefault();
    ev.stopPropagation();
    const targetBlock =
      mode === "resize-start" || mode === "resize-end" ? ev.currentTarget.closest(".event-block") : ev.currentTarget;
    if (!targetBlock) return;
    const pointerId = ev.pointerId ?? `mouse-${Date.now()}`;
    targetBlock.setPointerCapture?.(pointerId);
    dragState = {
      pointerId,
      mode,
      block: targetBlock,
      segment,
      eventData: segment.ev,
      originalStart: new Date(segment.ev.start),
      originalEnd: new Date(segment.ev.end),
      dayIdx: segment.dayIdx,
      pointerStartX: ev.clientX,
      pointerStartY: ev.clientY,
      scrollStartTop: timelineScroll?.scrollTop || 0,
      scrollStartLeft: timelineScroll?.scrollLeft || 0,
      initialTop: parseFloat(targetBlock.style.top) || 0,
      initialLeft: parseFloat(targetBlock.style.left) || 0,
      initialHeight: parseFloat(targetBlock.style.height) || targetBlock.getBoundingClientRect().height,
      initialWidth: parseFloat(targetBlock.style.width) || targetBlock.getBoundingClientRect().width,
      previewStart: null,
      previewEnd: null,
      hasMoved: false,
    };
    targetBlock.classList.add("event-block--editing");
    document.body.classList.add("user-select-none");
    window.addEventListener("pointermove", handleEventDragMove);
    window.addEventListener("pointerup", handleEventDragEnd);
  }

  function handleEventDragMove(ev) {
    if (!dragState || (dragState.pointerId && ev.pointerId && dragState.pointerId !== ev.pointerId)) return;
    const scrollTop = timelineScroll?.scrollTop || 0;
    const deltaYpx = ev.clientY - dragState.pointerStartY + (scrollTop - dragState.scrollStartTop);
    const deltaSlots = Math.round(deltaYpx / ROW_HEIGHT);
    const snappedDeltaY = deltaSlots * ROW_HEIGHT;
    const deltaMinutes = deltaSlots * SLOT_MINUTES;
    let dayShift = 0;
    if (dragState.mode === "move") {
      const scrollLeft = timelineScroll?.scrollLeft || 0;
      const deltaXpx = ev.clientX - dragState.pointerStartX + (scrollLeft - dragState.scrollStartLeft);
      const perDay = timelineMetrics?.dayWidth || 1;
      dayShift = Math.round(deltaXpx / perDay);
      const maxRight = timelineMetrics.dayCount - 1 - dragState.dayIdx;
      const maxLeft = -dragState.dayIdx;
      if (dayShift > maxRight) dayShift = maxRight;
      if (dayShift < maxLeft) dayShift = maxLeft;
      dragState.block.style.left = `${dragState.initialLeft + dayShift * perDay}px`;
      dragState.block.style.top = `${dragState.initialTop + snappedDeltaY}px`;
      if (dayShift !== 0 || deltaSlots !== 0) dragState.hasMoved = true;
    } else if (dragState.mode === "resize-start") {
      const bottom = dragState.initialTop + dragState.initialHeight;
      const newTop = Math.min(bottom - ROW_HEIGHT, dragState.initialTop + snappedDeltaY);
      const newHeight = bottom - newTop;
      dragState.block.style.top = `${newTop}px`;
      dragState.block.style.height = `${Math.max(ROW_HEIGHT, newHeight)}px`;
      if (deltaSlots !== 0) dragState.hasMoved = true;
    } else if (dragState.mode === "resize-end") {
      const newHeight = Math.max(ROW_HEIGHT, dragState.initialHeight + snappedDeltaY);
      dragState.block.style.height = `${newHeight}px`;
      if (deltaSlots !== 0) dragState.hasMoved = true;
    }
    const { start, end } = computeDragTimes(deltaMinutes, dayShift);
    dragState.previewStart = start;
    dragState.previewEnd = end;

    // Update time label in real-time
    const timeLabel = dragState.block.querySelector(".event-block-time");
    if (timeLabel) {
      const s = start.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
      const e = end.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
      timeLabel.textContent = `${s}-${e}`;
    }
  }

  function computeDragTimes(deltaMinutes, dayShift) {
    let start = new Date(dragState.originalStart);
    let end = new Date(dragState.originalEnd);
    if (dragState.mode === "move") {
      start = new Date(start.getTime() + dayShift * DAY_MS + deltaMinutes * 60000);
      end = new Date(end.getTime() + dayShift * DAY_MS + deltaMinutes * 60000);
    } else if (dragState.mode === "resize-start") {
      start = new Date(start.getTime() + deltaMinutes * 60000);
      if (start.getTime() >= end.getTime()) start = new Date(end.getTime() - SLOT_MINUTES * 60000);
    } else if (dragState.mode === "resize-end") {
      end = new Date(end.getTime() + deltaMinutes * 60000);
      if (end.getTime() <= start.getTime()) end = new Date(start.getTime() + SLOT_MINUTES * 60000);
    }
    return { start, end };
  }

  function handleEventDragEnd(ev) {
    if (!dragState || (dragState.pointerId && ev.pointerId && dragState.pointerId !== ev.pointerId)) return;
    const moved = dragState.hasMoved;
    dragState.block.classList.remove("event-block--editing");
    dragState.block.style.left = `${dragState.initialLeft}px`;
    dragState.block.style.top = `${dragState.initialTop}px`;
    dragState.block.style.height = `${dragState.initialHeight}px`;
    dragState.block.dataset.skipClick = moved ? "1" : dragState.block.dataset.skipClick;
    dragState.block.releasePointerCapture?.(dragState.pointerId);
    document.body.classList.remove("user-select-none");
    window.removeEventListener("pointermove", handleEventDragMove);
    window.removeEventListener("pointerup", handleEventDragEnd);
    const newStart = dragState.previewStart;
    const newEnd = dragState.previewEnd;
    const eventId = dragState.eventData?.id;
    const originalStartMs = dragState.originalStart.getTime();
    const originalEndMs = dragState.originalEnd.getTime();
    dragState = null;
    if (!newStart || !newEnd || !eventId) return;
    if (newStart.getTime() === originalStartMs && newEnd.getTime() === originalEndMs) {
      renderCalendar();
      return;
    }
    persistEventChange(eventId, newStart, newEnd);
  }

  async function persistEventChange(eventId, newStart, newEnd) {
    const evData = events.find((ev) => `${ev.id}` === `${eventId}`);
    if (!evData) {
      renderCalendar();
      return;
    }
    const payload = {
      title: evData.title,
      description: evData.description || "",
      start_time: formatLocalPayload(newStart),
      end_time: formatLocalPayload(newEnd),
      status: evData.status || DEFAULT_STATUS,
    };
    try {
      const res = await fetch(`/api/calendar/${eventId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-Timezone": clientTimeZone },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(`No se pudo actualizar: ${data.error || res.statusText}`);
        renderCalendar();
        return;
      }
      evData.start = newStart;
      evData.end = newEnd;
      evData.status = evData.status || DEFAULT_STATUS;
      renderCalendar();
      updateAppointmentRow(evData);
    } catch (error) {
      console.error("Error actualizando cita arrastrada:", error);
      alert("Error actualizando la cita");
      renderCalendar();
    }
  }

  function updateAppointmentRow(ev) {
    if (!ev || typeof ev.id === "undefined") return;
    const card = document.querySelector(`.appointment-card[data-appointment-id="${ev.id}"]`);
    if (!card) return;

    // Update Title
    const titleEl = card.querySelector(".app-title");
    if (titleEl) {
      titleEl.textContent = ev.title || "";
      titleEl.title = ev.title || "";
    }

    // Update Time
    const timeContainer = card.querySelector(".app-time");
    if (timeContainer) {
      // We know the structure is SVG, span(date), span(sep), span(time)
      // Rebuilding is safer or targeting spans
      const spans = timeContainer.querySelectorAll("span");
      if (spans.length >= 3) {
        spans[0].textContent = ev.start ? new Date(ev.start).toLocaleString("es-ES").slice(0, 10) : "";
        spans[2].textContent = ev.start ? new Date(ev.start).toLocaleString("es-ES").slice(11, 16) : "";
      }
    }

    // Update Status
    const statusBadge = card.querySelector(".status-badge");
    if (statusBadge) {
      statusBadge.className = `status-badge status-${ev.status || DEFAULT_STATUS}`;
      statusBadge.textContent = STATUS_LABELS[ev.status] || ev.status || DEFAULT_STATUS;
      // Re-apply inline styles if needed, or rely on CSS
      statusBadge.style.fontSize = "0.65rem";
      statusBadge.style.padding = "0.1rem 0.4rem";
    }

    // Update Edit Button onclick
    const editBtn = card.querySelector("button.btn-icon-soft.primary");
    if (editBtn) {
      const startForm = ev.start ? formatLocalPayload(new Date(ev.start)) : "";
      const endForm = ev.end ? formatLocalPayload(new Date(ev.end)) : "";
      // Escape strings
      const safeTitle = (ev.title || "").replace(/'/g, "&#39;");
      const safeDesc = (ev.description || "").replace(/'/g, "&#39;");
      editBtn.setAttribute(
        "onclick",
        `openEdit(${ev.id}, '${safeTitle}', '${safeDesc}', '${startForm}', '${endForm}', '${ev.status || DEFAULT_STATUS}', ${ev.client_id == null ? "null" : ev.client_id})`
      );
    }
  }

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(renderCalendar, 100);
  });

  function renderCalendar() {
    console.log("renderCalendar view", currentView, "anchor", anchorDate);
    if (currentView === "month") renderMonth();
    else renderTimeline(currentView);
    localStorage.setItem("calendar.anchor", String(anchorDate.getTime()));
  }
  window.__renderCalendar = renderCalendar;

  function handleSlotDown() {
    selecting = true;
    selectionStartTs = new Date(this.dataset.start).getTime();
    lastHoverTs = selectionStartTs;
    clearSelectionHighlight();
    this.classList.add("slot-selected");
    selectedSlots = [this];
  }
  function handleSlotEnter() { if (selecting) { lastHoverTs = new Date(this.dataset.start).getTime(); updateSelectionHighlight(); } }
  function handleSlotUp() { if (selecting) { lastHoverTs = new Date(this.dataset.start).getTime(); finalizeSelection(); } }

  function clearSelectionHighlight() {
    selectedSlots.forEach((s) => s.classList.remove("slot-selected"));
    selectedSlots = [];
  }
  function updateSelectionHighlight() {
    if (selectionStartTs === null || lastHoverTs === null) return;
    const minTs = Math.min(selectionStartTs, lastHoverTs);
    const maxTs = Math.max(selectionStartTs, lastHoverTs) + SLOT_MINUTES * 60000;
    clearSelectionHighlight();
    timelineBody?.querySelectorAll(".time-slot").forEach((slot) => {
      const ts = new Date(slot.dataset.start).getTime();
      if (ts >= minTs && ts <= maxTs) {
        slot.classList.add("slot-selected");
        selectedSlots.push(slot);
      }
    });
  }
  async function finalizeSelection() {
    if (selectionStartTs === null) {
      selecting = false;
      return;
    }
    const endTs = lastHoverTs !== null ? lastHoverTs : selectionStartTs + SLOT_MINUTES * 60000;
    const startTs = Math.min(selectionStartTs, endTs);
    const finalEnd = Math.max(startTs + SLOT_MINUTES * 60000, Math.max(selectionStartTs, endTs) + SLOT_MINUTES * 60000);
    clearSelectionHighlight();
    selecting = false;
    await openCreateModal(new Date(startTs), new Date(finalEnd));
    selectionStartTs = null;
    lastHoverTs = null;
  }
  window.addEventListener("mouseup", () => { if (selecting) finalizeSelection(); });

  // Modal detalle/edicion + eliminar
  const eventDetailModalEl = document.createElement("div");
  eventDetailModalEl.className = "modal fade";
  eventDetailModalEl.innerHTML = `
    <div class="modal-dialog"><div class="modal-content">
      <div class="modal-header"><h5 class="modal-title">Detalle de cita</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
      <form id="eventDetailForm">
        <div class="modal-body">
          <div class="mb-2"><label class="form-label">Titulo</label><input type="text" class="form-control" id="detailTitle" required></div>
          <div class="mb-2"><label class="form-label">Notas</label><textarea class="form-control" id="detailDesc" rows="2"></textarea></div>
          <div class="row g-2">
            <div class="col"><label class="form-label">Inicio</label><input type="datetime-local" class="form-control" id="detailStart" required></div>
            <div class="col"><label class="form-label">Fin</label><input type="datetime-local" class="form-control" id="detailEnd" required></div>
          </div>
          <div class="mt-3">
            <label class="form-label">Cliente (opcional)</label>
            <select class="form-select" id="detailClient"></select>
          </div>
          <div class="mt-3">
            <label class="form-label">Estado</label>
            <select class="form-select" id="detailStatus">
              ${renderStatusOptions()}
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-danger me-auto" id="detailDeleteBtn">Eliminar</button>
          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cerrar</button>
          <button type="submit" class="btn btn-primary">Guardar cambios</button>
        </div>
      </form>
    </div></div>`;
  document.body.appendChild(eventDetailModalEl);
  const eventDetailModal = new bootstrap.Modal(eventDetailModalEl);
  const detailForm = eventDetailModalEl.querySelector("#eventDetailForm");
  const detailTitle = eventDetailModalEl.querySelector("#detailTitle");
  const detailDesc = eventDetailModalEl.querySelector("#detailDesc");
  const detailStart = eventDetailModalEl.querySelector("#detailStart");
  const detailEnd = eventDetailModalEl.querySelector("#detailEnd");
  const detailStatus = eventDetailModalEl.querySelector("#detailStatus");
  const detailClient = eventDetailModalEl.querySelector("#detailClient");
  const detailDeleteBtn = eventDetailModalEl.querySelector("#detailDeleteBtn");
  // currentEventId ya declarado arriba

  async function deleteEvent(id) {
    try {
      const res = await fetch(`${getApiBase()}/${id}`, { method: "DELETE", headers: { "X-Timezone": clientTimeZone } });
      if (!res.ok) return false;
      const idx = events.findIndex((ev) => `${ev.id}` === `${id}`);
      if (idx >= 0) events.splice(idx, 1);
      const row = document.querySelector(`.appointment-card[data-appointment-id="${id}"]`);
      if (row) row.remove();
      return true;
    } catch {
      return false;
    }
  }

  const emitCalendarChanged = () => {
    try {
      window.dispatchEvent(new CustomEvent("vetflow:calendarChanged"));
    } catch {
      // ignore
    }
  };
  const clientTimeZone = (() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch {
      return "";
    }
  })();

  function openEventModal(item) {
    // Compat: a veces se llama con {ev, start, end} (render timeline),
    // y otras con el evento directo.
    const ev = item?.ev || item;
    const start = ev?.start || item?.start;
    const end = ev?.end || item?.end;
    if (!ev || ev.id === undefined || ev.id === null) return;
    currentEventId = ev.id;
    detailTitle.value = ev.title || "";
    detailDesc.value = ev.description || "";
    detailStart.value = toInput(start?.toISOString ? start.toISOString() : start);
    detailEnd.value = toInput(end?.toISOString ? end.toISOString() : end);
    detailStatus.value = ev.status || DEFAULT_STATUS;

    const currentClientId = ev.client_id ?? null;
    if (detailClient) {
      populateClientSelect(detailClient, currentClientId, clientsCache || []);
      if (!Array.isArray(clientsCache)) {
        detailClient.disabled = true;
        void ensureClientsLoaded()
          .then((clients) => populateClientSelect(detailClient, currentClientId, clients))
          .finally(() => {
            detailClient.disabled = false;
          });
      }
    }
    // detailTimezone.value = ev.timezone || ""; // si lo hubieramos implementado en modal detalle

    const startDate = start instanceof Date ? start : new Date(start);
    const endDate = end instanceof Date ? end : new Date(end);
    currentEventSnapshot = {
      title: detailTitle.value,
      description: detailDesc.value,
      status: detailStatus.value,
      clientId: detailClient?.value || "",
      startMs: !isNaN(startDate?.getTime?.()) ? startDate.getTime() : null,
      endMs: !isNaN(endDate?.getTime?.()) ? endDate.getTime() : null,
    };
    eventDetailModal.show();
  }

  detailForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentEventId) {
      eventDetailModal.hide();
      return;
    }
    const startVal = new Date(detailStart.value);
    const endVal = new Date(detailEnd.value);
    if (endVal <= startVal) {
      alert("El fin debe ser mayor que el inicio");
      return;
    }
    const nextTitle = detailTitle.value.trim();
    const nextDesc = detailDesc.value.trim();
    const nextStatus = detailStatus.value || DEFAULT_STATUS;
    const nextClientRaw = detailClient?.value || "";

    const payload = {};
    if (!currentEventSnapshot || currentEventSnapshot.title !== nextTitle) payload.title = nextTitle;
    if (!currentEventSnapshot || currentEventSnapshot.description !== nextDesc) payload.description = nextDesc;
    if (!currentEventSnapshot || currentEventSnapshot.status !== nextStatus) payload.status = nextStatus;
    if (!currentEventSnapshot || currentEventSnapshot.clientId !== nextClientRaw) {
      if (!nextClientRaw) payload.client_id = null;
      else {
        const parsed = parseInt(nextClientRaw, 10);
        payload.client_id = Number.isFinite(parsed) ? parsed : null;
      }
    }

    const startMs = startVal.getTime();
    const endMs = endVal.getTime();
    if (!currentEventSnapshot || currentEventSnapshot.startMs !== startMs) payload.start_time = formatLocalPayload(startVal);
    if (!currentEventSnapshot || currentEventSnapshot.endMs !== endMs) payload.end_time = formatLocalPayload(endVal);

    if (!Object.keys(payload).length) {
      eventDetailModal.hide();
      return;
    }
    try {
      const res = await fetch(`${getApiBase()}/${currentEventId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-Timezone": clientTimeZone },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        eventDetailModal.hide();
        const idx = events.findIndex((ev) => ev.id === currentEventId);
        if (idx >= 0) {
          const nextEv = {
            ...events[idx],
            title: payload.title ?? events[idx].title,
            description: payload.description ?? events[idx].description,
            status: payload.status ?? events[idx].status,
            timezone: payload.timezone ?? events[idx].timezone,
            start: payload.start_time ? new Date(payload.start_time) : events[idx].start,
            end: payload.end_time ? new Date(payload.end_time) : events[idx].end,
          };
          if ("client_id" in payload) nextEv.client_id = payload.client_id;
          events[idx] = nextEv;
        }
        emitCalendarChanged();
        renderCalendar();
      } else alert(`No se pudo actualizar: ${data.error || res.statusText}`);
    } catch {
      alert("Error actualizando la cita");
    }
  });

  detailDeleteBtn?.addEventListener("click", async () => {
    if (!currentEventId) return;
    if (!confirm("Eliminar esta cita?")) return;
    const ok = await deleteEvent(currentEventId);
    if (ok) {
      eventDetailModal.hide();
      emitCalendarChanged();
      renderCalendar();
    } else alert("No se pudo eliminar la cita");
  });

  async function openCreateModal(startDate, endDate) {
    if (!createEventModal) createEventModal = new bootstrap.Modal(createEventModalEl);
    if (eventTitleInput) eventTitleInput.value = "";
    if (eventDescInput) eventDescInput.value = "";
    if (eventStatusSelect) eventStatusSelect.value = DEFAULT_STATUS;
    if (eventClientSelect) {
      populateClientSelect(eventClientSelect, null, clientsCache || []);
      eventClientSelect.value = "";
      if (!Array.isArray(clientsCache)) {
        eventClientSelect.disabled = true;
        void ensureClientsLoaded()
          .then((clients) => populateClientSelect(eventClientSelect, null, clients))
          .finally(() => {
            eventClientSelect.disabled = false;
          });
      }
    }
    const rangeStart = startDate || getRoundedDefaultRange().start;
    const rangeEnd = endDate || new Date(rangeStart.getTime() + SLOT_MINUTES * 2 * 60000);
    primeCreateModalRange(rangeStart, rangeEnd);
    createEventModal.show();
    setTimeout(() => eventTitleInput?.focus(), 120);
  }

  // Exponer helpers para integraciones (FullCalendar)
  window.vetflowCalendar = window.vetflowCalendar || {};
  window.vetflowCalendar.openCreateModal = openCreateModal;
  window.vetflowCalendar.openEventModal = openEventModal;
  window.vetflowCalendar.refresh = renderCalendar;

  createEventForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = eventTitleInput.value.trim();
    if (!title) {
      eventTitleInput.focus();
      return;
    }
    const startRaw = eventStartInput?.value || eventStartIso?.value;
    const endRaw = eventEndInput?.value || eventEndIso?.value;
    const startVal = startRaw ? new Date(startRaw) : null;
    const endVal = endRaw ? new Date(endRaw) : null;
    if (!startVal || !endVal || isNaN(startVal.getTime()) || isNaN(endVal.getTime())) {
      alert("Completa las fechas de inicio y fin");
      return;
    }
    if (endVal <= startVal) {
      alert("El fin debe ser mayor que el inicio");
      return;
    }
    const payload = {
      title,
      description: eventDescInput.value.trim(),
      start_time: formatLocalPayload(startVal),
      end_time: formatLocalPayload(endVal),
      status: eventStatusSelect?.value || DEFAULT_STATUS,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
    };
    const clientRaw = eventClientSelect?.value || "";
    if (clientRaw) {
      const parsed = parseInt(clientRaw, 10);
      if (Number.isFinite(parsed)) payload.client_id = parsed;
    }
    try {
      const res = await fetch(getApiBase(), { method: "POST", headers: { "Content-Type": "application/json", "X-Timezone": clientTimeZone }, body: JSON.stringify(payload) });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        createEventModal.hide();
        const newEv = {
          ...data,
          start: new Date(payload.start_time),
          end: new Date(payload.end_time),
          title: data.title || payload.title,
          description: data.description || payload.description,
          status: data.status || payload.status || DEFAULT_STATUS,
        };
        events.push(newEv);
        emitCalendarChanged();
        renderCalendar();
        appendAppointmentRow(newEv);
      } else alert(`No se pudo crear la cita: ${data.error || res.statusText}`);
    } catch {
      alert("Error creando la cita");
    }
  });

  function appendAppointmentRow(ev) {
    if (!appointmentsTableBody) return;
    const div = document.createElement("div");
    div.className = "appointment-card";
    div.setAttribute("data-appointment-id", ev.id || "");
    const eventStatus = ev.status || DEFAULT_STATUS;
    const startForm = ev.start ? formatLocalPayload(ev.start) : "";
    const endForm = ev.end ? formatLocalPayload(ev.end) : "";
    const startTimeStr = ev.start ? formatDateYMD(ev.start) : "";
    const startTimeHour = ev.start ? formatHourHM(ev.start) : "";
    const startData = ev.start ? ev.start.toISOString() : "";
    const clientIdParam = ev.client_id == null ? "null" : ev.client_id;

    div.innerHTML = `
      <div class="form-check m-0">
        <input type="checkbox" class="form-check-input appointment-check" value="${ev.id || ""}" style="width: 1.2rem; height: 1.2rem; border-color: #d1c4e9;">
      </div>
      <div class="flex-grow-1">
        <div class="d-flex justify-content-between align-items-start mb-1">
          <div class="app-title text-truncate" style="max-width: 160px;" title="${ev.title || ""}">${ev.title || ""}</div>
          ${renderStatusBadge(eventStatus)}
        </div>
        <div class="app-time">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span class="appointment-date" data-datetime="${startData}">${startTimeStr}</span>
          <span class="text-muted mx-1">•</span>
          <span class="appointment-hour" data-datetime="${startData}">${startTimeHour}</span>
          <span class="appointment-timezone text-muted ms-1 small opacity-0 transition-opacity"></span>
        </div>
      </div>
      <div class="d-flex flex-column gap-1">
        <button class="btn-icon-soft primary" type="button"
          onclick="openEdit(${ev.id || ""}, '${(ev.title || "").replace(/'/g, "&#39;")}', '${(ev.description || "").replace(/'/g, "&#39;")}', '${startForm}', '${endForm}', '${eventStatus}', ${clientIdParam})"
          title="Editar">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
          </svg>
        </button>
        </button>
        <button class="btn-icon-soft danger" type="button" title="Eliminar" onclick="
          if(confirm('Eliminar esta cita?')) {
            window.deleteEvent(${ev.id}).then(ok => {
              if(!ok) alert('No se pudo eliminar');
            });
          }
        ">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>`;

    // Adjust badge styling manually since renderStatusBadge creates a span without the extra styles
    const badge = div.querySelector(".status-badge");
    if (badge) {
      badge.style.fontSize = "0.65rem";
      badge.style.padding = "0.1rem 0.4rem";
    }

    appointmentsTableBody.prepend(div);
    div.querySelectorAll(".appointment-check").forEach((ch) => ch.addEventListener("change", updateBulkState));
    hydrateAppointmentTimes(div);
  }

  // Controles
  if (hasLegacyCalendarSurface) {
    prevMonthBtn?.addEventListener("click", () => shiftPeriod(-1));
    nextMonthBtn?.addEventListener("click", () => shiftPeriod(1));
    todayBtn?.addEventListener("click", () => {
      anchorDate = new Date();
      localStorage.setItem("calendar.anchor", String(anchorDate.getTime()));
      renderCalendar();
    });
    viewButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.calendarView === currentView);
      btn.addEventListener("click", () => setView(btn.dataset.calendarView));
    });
  }
  // El botón "Nueva cita" se mantiene para reusar el mismo modal en FullCalendar.
  quickEventBtn?.addEventListener("click", () => {
    const { start, end } = getRoundedDefaultRange();
    openCreateModal(start, end);
  });

  // Modal dia
  const dayEventsModalEl = document.getElementById("dayEventsModal");
  const dayEventsTitle = document.getElementById("dayEventsTitle");
  const dayEventsBody = document.getElementById("dayEventsBody");
  let dayEventsModal;
  function showDayEvents(day, dayEvents) {
    dayEventsTitle.textContent = day.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    dayEventsBody.innerHTML = "";
    if (!dayEvents.length) {
      dayEventsBody.innerHTML = '<p class="text-muted mb-0">Sin citas</p>';
    } else {
      dayEvents.forEach((ev) => {
        const startHour = ev.start.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
        const endHour = ev.end.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
        const div = document.createElement("div");
        div.className = "border rounded p-2 mb-2";
        div.innerHTML = `<div class="fw-semibold">${ev.title}</div><div class="text-muted">${startHour} - ${endHour}</div>${ev.description ? `<div>${ev.description}</div>` : ""}`;
        dayEventsBody.appendChild(div);
      });
    }
    dayEventsModal = dayEventsModal || new bootstrap.Modal(dayEventsModalEl);
    dayEventsModal.show();
  }

  document.addEventListener("DOMContentLoaded", () => {
    try {
      loadThumbnails();
      hydrateAppointmentTimes();
      const initialTab = localStorage.getItem("ui.activeTab") || "calendar";
      if (!localStorage.getItem("ui.activeTab")) {
        localStorage.setItem("ui.activeTab", initialTab);
      }
      if (initialTab === "calendar") {
        const tabEl = document.querySelector("#calendar-tab");
        if (tabEl) new bootstrap.Tab(tabEl).show();
      }
      if (hasLegacyCalendarSurface) {
        renderCalendar();
      }
    } catch (err) {
      console.error("Error inicializando calendario:", err);
    }
  });

  function hydrateAppointmentTimes(scope) {
    const root = scope || document;
    root.querySelectorAll(".appointment-date[data-datetime]").forEach((el) => {
      const raw = el.getAttribute("data-datetime");
      const d = raw ? new Date(raw) : null;
      if (!d || isNaN(d.getTime())) return;
      el.textContent = formatDateYMD(d);
      el.classList.remove("opacity-0");
    });
    root.querySelectorAll(".appointment-hour[data-datetime]").forEach((el) => {
      const raw = el.getAttribute("data-datetime");
      const d = raw ? new Date(raw) : null;
      if (!d || isNaN(d.getTime())) return;
      el.textContent = formatHourHM(d);
      el.classList.remove("opacity-0");
    });
    root.querySelectorAll(".appointment-timezone").forEach((el) => {
      // Intenta obtener algo corto como "GMT-5"
      try {
        const txt = Intl.DateTimeFormat().resolvedOptions().timeZone;
        el.textContent = txt;
        el.classList.remove("opacity-0");
      } catch {
        el.textContent = "";
      }
    });
  }

  document.querySelectorAll("button[data-bs-toggle='tab']").forEach((btn) => {
    btn.addEventListener("shown.bs.tab", (e) => {
      const targetId = e.target.getAttribute("data-bs-target")?.replace("#", "") || "";
      if (targetId) localStorage.setItem("ui.activeTab", targetId);
    });
  });

  // Replaced static listener with delegation to handle potential DOM updates
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('#bulkDeleteBtn');
    if (!btn) return;

    // Prevent default just in case
    e.preventDefault();

    const checks = Array.from(document.querySelectorAll(".appointment-check:checked"));
    const ids = checks.map((ch) => ch.value);

    if (!ids.length) return;

    if (!confirm(`¿Estás seguro de que quieres eliminar ${ids.length} cita(s)?`)) return;

    // UI Feedback
    const originalContent = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>`;

    let deletedCount = 0;
    try {
      for (const id of ids) {
        const ok = await deleteEvent(id);
        if (ok) deletedCount++;
      }
    } catch (err) {
      console.error("Error en borrado masivo", err);
    } finally {
      // Restore UI
      btn.innerHTML = originalContent;
      updateBulkState(); // Re-evaluates disabled state based on remaining checks (if any)

      if (deletedCount > 0) {
        emitCalendarChanged();
        renderCalendar();
      }

      if (deletedCount < ids.length) {
        alert(`Se eliminaron ${deletedCount} de ${ids.length} citas.`);
      }
    }
  });

  // Refreshed updateBulkState to query fresh DOM elements
  function updateBulkState() {
    const btn = document.getElementById("bulkDeleteBtn");
    if (!btn) return;
    const checks = Array.from(document.querySelectorAll(".appointment-check"));
    const anyChecked = checks.some((ch) => ch.checked);
    btn.disabled = !anyChecked;

    if (selectAllAppointments) {
      const allChecked = checks.length > 0 && checks.every((ch) => ch.checked);
      selectAllAppointments.checked = allChecked;
      selectAllAppointments.indeterminate = anyChecked && !allChecked;
    }
  }

  // Robust delegation for all checkbox changes (individual and select-all)
  document.addEventListener('change', (e) => {
    if (e.target.matches('.appointment-check')) {
      updateBulkState();
    } else if (e.target && e.target.id === 'selectAllAppointments') {
      const val = e.target.checked;
      document.querySelectorAll(".appointment-check").forEach((ch) => (ch.checked = val));
      updateBulkState();
    }
  });

  // Expose for inline usage
  window.deleteEvent = deleteEvent;

  // Initialize bulk listeners if not already attached (redundant check if script runs late, but safe)
  if (document.readyState !== 'loading') {
    updateBulkState();
  } else {
    document.addEventListener('DOMContentLoaded', updateBulkState);
  }
})();
