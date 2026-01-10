(() => {
  const root = () => document.getElementById('fullCalendarRoot')
  const surface = () => document.getElementById('calendarSurface')
  const prevBtn = () => document.getElementById('prevMonth')
  const nextBtn = () => document.getElementById('nextMonth')
  const todayBtn = () => document.getElementById('todayBtn')
  const quickBtn = () => document.getElementById('openQuickEventBtn')
  const labelEl = () => document.getElementById('calendarMonthLabel')
  const metaEl = () => document.getElementById('calendarMonthMeta')
  const viewButtons = () => Array.from(document.querySelectorAll('[data-calendar-view]'))

  const pad2 = (n) => String(n).padStart(2, '0')
  const clamp = (n, min, max) => Math.max(min, Math.min(max, n))
  const scrollTimeAroundNow = () => {
    const now = new Date()
    // Centrar un poco antes para que se vea contexto "alrededor" de la hora actual
    const minutes = now.getHours() * 60 + now.getMinutes() - 60
    const clamped = clamp(minutes, 0, 23 * 60 + 59)
    const h = Math.floor(clamped / 60)
    const m = clamped % 60
    return `${pad2(h)}:${pad2(m)}:00`
  }

  const getWorkspaceSlug = () => {
    const slug = surface()?.getAttribute('data-workspace-slug') || ''
    return slug.trim()
  }

  const apiBase = () => {
    const slug = getWorkspaceSlug()
    return slug ? `/w/${encodeURIComponent(slug)}/api/calendar` : '/api/calendar'
  }

  const clientTimeZone = (() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || ''
    } catch {
      return ''
    }
  })()

  const toIso = (d) => {
    if (!d) return null
    const date = d instanceof Date ? d : new Date(d)
    return isNaN(date.getTime()) ? null : date.toISOString()
  }

  const toIsoWithLocalOffset = (d) => {
    if (!d) return null
    const date = d instanceof Date ? d : new Date(d)
    if (isNaN(date.getTime())) return null
    const pad2 = (n) => String(n).padStart(2, '0')
    const offsetMinutes = -date.getTimezoneOffset()
    const sign = offsetMinutes >= 0 ? '+' : '-'
    const abs = Math.abs(offsetMinutes)
    const offH = pad2(Math.floor(abs / 60))
    const offM = pad2(abs % 60)
    return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}T${pad2(date.getHours())}:${pad2(date.getMinutes())}:00${sign}${offH}:${offM}`
  }

  const statusColor = (status) => {
    const value = String(status || '').toLowerCase()
    if (value === 'confirmada') return '#2563eb'
    if (value === 'completada') return '#16a34a'
    if (value === 'cancelada') return '#dc2626'
    if (value === 'no_show') return '#f97316'
    return '#7c3aed' // programada/default
  }

  const WEEKDAY_LABELS = [
    'Domingo',
    'Lunes',
    'Martes',
    'Miercoles',
    'Jueves',
    'Viernes',
    'Sabado',
  ]
  const formatDayHeader = (value, viewType) => {
    const date = value instanceof Date ? value : new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    const label = WEEKDAY_LABELS[date.getDay()] || ''
    if (!label) return ''
    const upper = label.toUpperCase()
    if (viewType && !String(viewType).includes('Month')) {
      return `${upper} ${date.getDate()}/${date.getMonth() + 1}`
    }
    return upper
  }

  let calendar = null
  let enabled = true
  let hasRendered = false
  let hasScrolledInitial = false
  const LOCKED_STATUS_VALUES = ['cancelada', 'completada', 'no_show']
  const isStatusLocked = (status) => LOCKED_STATUS_VALUES.includes(String(status || '').toLowerCase())

  const setHeaderText = () => {
    const title = calendar?.view?.title || 'Calendario'
    const label = labelEl()
    const meta = metaEl()
    if (label) label.textContent = title
    if (meta) meta.textContent = ''
  }

  const syncViewButtons = () => {
    const type = calendar?.view?.type || 'dayGridMonth'
    const map = { dayGridMonth: 'month', timeGridWeek: 'week', timeGridDay: 'day' }
    const active = map[type] || 'month'
    viewButtons().forEach((b) => b.classList.toggle('active', b.getAttribute('data-calendar-view') === active))
  }

  const fixDayHeaderLabels = () => {
    const viewType = calendar?.view?.type || ''
    const cells = document.querySelectorAll('#fullCalendarRoot .fc-col-header-cell')
    if (!cells.length) return
    const rootStyles = getComputedStyle(document.documentElement)
    const mainColor = rootStyles.getPropertyValue('--vet-text-main').trim() || '#111827'
    cells.forEach((cell) => {
      const dateStr = cell.getAttribute('data-date') || ''
      const cushion = cell.querySelector('.fc-col-header-cell-cushion')
      if (!cushion) return
      const label = formatDayHeader(dateStr, viewType)
      if (label) cushion.textContent = label
      cushion.style.visibility = 'visible'
      cushion.style.opacity = '1'
      cushion.style.color = mainColor
      cell.style.visibility = 'visible'
      cell.style.opacity = '1'
    })
  }

  const getFirstDayIndex = () => {
    const value = calendar?.getOption ? calendar.getOption('firstDay') : 0
    return Number.isFinite(value) ? value : 0
  }

  const ensureWeekdayStrip = () => {
    const toolbarEl =
      document.querySelector('#calendar .calendar-app-toolbar') ||
      document.querySelector('.calendar-app-toolbar')
    if (!toolbarEl) return null
    let strip = toolbarEl.querySelector('#calendarWeekdayStrip')
    if (!strip) {
      strip = document.createElement('div')
      strip.id = 'calendarWeekdayStrip'
      strip.className = 'calendar-weekday-strip d-none'
      toolbarEl.appendChild(strip)
    }
    return strip
  }

  const renderWeekdayStrip = () => {
    const strip = ensureWeekdayStrip()
    if (!strip || !calendar?.view) return
    const viewType = calendar.view.type || ''
    const isTimeGrid = viewType.startsWith('timeGrid')
    const isDayGrid = viewType.startsWith('dayGrid')

    if (!isTimeGrid && !isDayGrid) {
      strip.classList.add('d-none')
      document.body.classList.remove('fc-custom-weekdays')
      return
    }

    strip.classList.remove('d-none')
    strip.setAttribute('data-view', isTimeGrid ? 'timegrid' : 'daygrid')
    strip.innerHTML = ''

    if (isTimeGrid) {
      const axisEl = document.querySelector('#fullCalendarRoot .fc-timegrid-axis')
      const axisWidth = axisEl ? Math.round(axisEl.getBoundingClientRect().width) : 0
      strip.style.setProperty('--fc-axis-width', `${axisWidth}px`)
      const axisCell = document.createElement('div')
      axisCell.className = 'calendar-weekday-axis'
      strip.appendChild(axisCell)

      const start = new Date(calendar.view.activeStart)
      const end = new Date(calendar.view.activeEnd)
      const days = []
      for (let d = new Date(start); d < end; d.setDate(d.getDate() + 1)) {
        days.push(new Date(d))
      }
      strip.style.setProperty('--fc-day-count', String(days.length || 1))
      days.forEach((day) => {
        const cell = document.createElement('div')
        cell.className = 'calendar-weekday-cell'
        cell.textContent = formatDayHeader(day, viewType)
        strip.appendChild(cell)
      })
    } else {
      strip.style.setProperty('--fc-axis-width', '0px')
      strip.style.setProperty('--fc-day-count', '7')
      const firstDay = getFirstDayIndex()
      for (let i = 0; i < 7; i += 1) {
        const dayIndex = (firstDay + i) % 7
        const label = (WEEKDAY_LABELS[dayIndex] || '').toUpperCase()
        const cell = document.createElement('div')
        cell.className = 'calendar-weekday-cell'
        cell.textContent = label
        strip.appendChild(cell)
      }
    }
    document.body.classList.add('fc-custom-weekdays')
  }

  const fetchEvents = async (info, success, failure) => {
    try {
      const res = await fetch(apiBase(), { headers: { Accept: 'application/json', 'X-Timezone': clientTimeZone } })
      const data = await res.json().catch(() => [])
      if (!res.ok) throw new Error(data?.error || `Error ${res.status}`)

      const events = (Array.isArray(data) ? data : []).map((a) => ({
        id: String(a.id),
        title: a.title || '(Sin título)',
        start: a.start_time,
        end: a.end_time,
        backgroundColor: statusColor(a.status),
        borderColor: statusColor(a.status),
        extendedProps: {
          status: a.status,
          description: a.description || '',
          client_id: a.client_id ?? null,
        },
      }))
      success(events)
    } catch (err) {
      console.error('FullCalendar fetchEvents', err)
      failure(err)
    }
  }

  const openCreateForm = async (start, end) => {
    const handler = window.vetflowCalendar?.openCreateModal
    if (typeof handler === 'function') {
      await handler(start, end)
      return
    }
    alert('No se encontró el formulario de creación (calendar.js)')
  }

  const updateEvent = async (event) => {
    const id = event?.id
    if (!id) return
    if (isStatusLocked(event.extendedProps?.status)) {
      throw new Error('Esta cita está bloqueada por su estado')
    }
    const payload = {
      title: event.title,
      start_time: toIsoWithLocalOffset(event.start),
      end_time: toIsoWithLocalOffset(event.end || event.start),
    }
    const base = apiBase()
    const url = `${base}/${encodeURIComponent(id)}`
    const res = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-Timezone': clientTimeZone },
      body: JSON.stringify(payload),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.error || `Error ${res.status}`)
  }

  const deleteEvent = async (event) => {
    const id = event?.id
    if (!id) return
    if (!confirm('¿Eliminar esta cita?')) return
    const base = apiBase()
    const url = `${base}/${encodeURIComponent(id)}`
    const res = await fetch(url, { method: 'DELETE', headers: { Accept: 'application/json', 'X-Timezone': clientTimeZone } })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.error || `Error ${res.status}`)
    calendar?.refetchEvents()
  }

  const ensureCalendar = () => {
    if (calendar) return
    const container = root()
    if (!container) return
    if (!window.FullCalendar?.Calendar) {
      console.warn('FullCalendar global no disponible')
      return
    }
    calendar = new window.FullCalendar.Calendar(container, {
      // Default: vista diaria tipo agenda
      initialView: 'timeGridDay',
      // Altura fija para habilitar scroll vertical en timeGrid
      height: 650,
      locale: 'es',
      firstDay: 1,
      selectable: true,
      editable: true,
      nowIndicator: true,
      dayMaxEvents: true,
      dayHeaders: true,
      dayHeaderFormat: { weekday: 'short' },
      dayHeaderContent: (args) => formatDayHeader(args.date, args.view?.type),
      dayHeaderDidMount: (args) => {
        if (!args?.el) return
        const next = formatDayHeader(args.date, args.view?.type)
        if (next && !args.el.textContent.trim()) args.el.textContent = next
      },
      // Mantener el día completo, pero iniciar scrolleado a las 08:00 (permite subir/bajar)
      slotMinTime: '00:00:00',
      slotMaxTime: '24:00:00',
      scrollTime: scrollTimeAroundNow(),
      scrollTimeReset: false,
      slotDuration: '00:30:00',
      expandRows: false,
      allDaySlot: false,
      // Usamos la toolbar del panel (no la de FullCalendar) para evitar duplicados.
      headerToolbar: false,
      events: fetchEvents,
      select: async (selectionInfo) => {
        try {
          await openCreateForm(selectionInfo.start, selectionInfo.end)
        } catch (err) {
          alert(err?.message || 'No se pudo crear la cita')
        } finally {
          calendar?.unselect()
        }
      },
      eventDrop: async (info) => {
        try {
          await updateEvent(info.event)
        } catch (err) {
          info.revert()
          alert(err?.message || 'No se pudo mover la cita')
        }
      },
      eventResize: async (info) => {
        try {
          await updateEvent(info.event)
        } catch (err) {
          info.revert()
          alert(err?.message || 'No se pudo redimensionar la cita')
        }
      },
      eventClick: async (info) => {
        try {
          // Reutilizar el mismo formulario/estilo del panel (cartillas + modal)
          if (typeof window.openEdit === 'function') {
            const ev = info.event
            window.openEdit(
              Number(ev.id),
              String(ev.title || ''),
              String(ev.extendedProps?.description || ''),
              toIso(ev.start),
              toIso(ev.end || ev.start),
              String(ev.extendedProps?.status || 'programada'),
              ev.extendedProps?.client_id ?? null
            )
            return
          }
        } catch (err) {
          alert(err?.message || 'Acción falló')
          calendar?.refetchEvents()
        }
      },
      datesSet: () => {
        setHeaderText()
        syncViewButtons()
        fixDayHeaderLabels()
        setTimeout(fixDayHeaderLabels, 50)
        renderWeekdayStrip()
        setTimeout(renderWeekdayStrip, 50)
      },
    })
  }

  const isCalendarTabActive = () => {
    const pane = document.getElementById('calendar')
    return !!(pane && pane.classList.contains('active'))
  }

  const checkLayout = () => {
    if (!calendar) return
    const container = root()
    if (!container || container.offsetParent === null) return

    try {
      calendar.updateSize()
    } catch (e) { /* ignore */ }

    if (!hasScrolledInitial) {
      if (String(calendar.view?.type || '').startsWith('timeGrid')) {
        try {
          calendar.scrollToTime(scrollTimeAroundNow())
          hasScrolledInitial = true
        } catch { /* ignore */ }
      } else {
        hasScrolledInitial = true
      }
    }
  }

  const renderIfVisible = async (forceRefetch = true) => {
    if (!enabled) return
    ensureCalendar()
    if (!calendar) return
    const container = root()
    if (!container) return
    if (!isCalendarTabActive()) return

    let justRendered = false
    if (!hasRendered) {
      calendar.render()
      hasRendered = true
      justRendered = true
    }

    checkLayout()
    fixDayHeaderLabels()
    setTimeout(fixDayHeaderLabels, 50)
    renderWeekdayStrip()
    setTimeout(renderWeekdayStrip, 50)

    // Only refetch if we didn't just render (render() fetches automatically)
    // and if forceRefetch is requested
    if (!justRendered && forceRefetch) {
      calendar.refetchEvents()
    }

    setHeaderText()
    syncViewButtons()
  }

  const scheduleRenderRetries = () => {
    // Phase 1: Immediate attempt with potential refetch
    void renderIfVisible(true)

    // Phase 2: Stabilization loop (adjust layout as CSS transitions finish)
    let attempts = 0
    const tick = () => {
      attempts++
      // Only check layout/render, do not force refetch
      void renderIfVisible(false)
      // Run for approx 2.5 seconds to cover slow transitions
      if (attempts < 25) setTimeout(tick, 100)
    }
    setTimeout(tick, 50)
  }

  document.addEventListener('DOMContentLoaded', () => {
    // Render inicial (y reintentos) para evitar pantalla en blanco tras F5.
    scheduleRenderRetries()

    // Render al activar la tab de calendario (tu UI usa data-tab-target)
    document.querySelectorAll('[data-tab-target="calendar"]').forEach((el) => {
      el.addEventListener('click', () => {
        // deja que la UI aplique clases y luego renderiza
        scheduleRenderRetries()
      })
    })

    // Si el usuario recarga con otra tab activa y luego vuelve a Calendario
    const pane = document.getElementById('calendar')
    if (pane) {
      const observer = new MutationObserver(() => {
        if (isCalendarTabActive()) setTimeout(() => void renderIfVisible(), 0)
      })
      observer.observe(pane, { attributes: true, attributeFilter: ['class'] })
    }

    prevBtn()?.addEventListener('click', () => {
      calendar.prev()
      setHeaderText()
    })
    nextBtn()?.addEventListener('click', () => {
      calendar.next()
      setHeaderText()
    })
    todayBtn()?.addEventListener('click', () => {
      calendar.today()
      setHeaderText()
      if (String(calendar.view?.type || '').startsWith('timeGrid')) {
        try {
          calendar.scrollToTime(scrollTimeAroundNow())
        } catch {
          // ignore
        }
      }
    })

    viewButtons().forEach((btn) => {
      btn.addEventListener('click', () => {
        const v = btn.getAttribute('data-calendar-view')
        const map = { month: 'dayGridMonth', week: 'timeGridWeek', day: 'timeGridDay' }
        const next = map[v] || 'dayGridMonth'
        calendar.changeView(next)
        syncViewButtons()
        setHeaderText()
      })
    })

    quickBtn()?.addEventListener('click', async () => {
      try {
        await openCreateForm(new Date(), new Date(Date.now() + 30 * 60 * 1000))
      } catch (err) {
        alert(err?.message || 'No se pudo abrir el formulario')
      }
    })

  window.addEventListener('resize', () => {
    if (isCalendarTabActive()) {
      try { calendar?.updateSize?.() } catch { /* ignore */ }
      renderWeekdayStrip()
    }
  })
  })

  window.addEventListener('load', () => {
    // Fallback: algunos estilos cargan tarde y FullCalendar necesita updateSize/render.
    scheduleRenderRetries()
  })

  window.addEventListener('vetflow:calendarTabActivated', () => {
    scheduleRenderRetries()
  })

  // Si el calendario "nativo" crea/actualiza/borrar (modales), refrescar FullCalendar
  window.addEventListener('vetflow:calendarChanged', () => {
    if (enabled) calendar?.refetchEvents()
  })
})()
