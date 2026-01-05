(() => {
  const panel = document.getElementById('clientesPanel')
  if (!panel) return

  const slug = (panel.getAttribute('data-workspace-slug') || '').trim()
  if (!slug) return

  const $ = (id) => document.getElementById(id)

  const listEl = $('clientesList')
  const hintEl = $('clientesListHint')
  const searchInput = $('clientesSearchInput')
  const refreshBtn = $('clientesRefreshBtn')
  const createForm = $('clientesCreateForm')
  const createStatus = $('clientesCreateStatus')

  const detailName = $('clienteDetailName')
  const detailMeta = $('clienteDetailMeta')
  const detailBody = $('clienteDetailBody')
  const emptyHint = $('clienteEmptyHint')
  const editBtn = $('clienteEditBtn')

  const phoneEl = $('clientePhone')
  const emailEl = $('clienteEmail')
  const identificationEl = $('clienteIdentification')
  const addressEl = $('clienteAddress')
  const notesEl = $('clienteNotes')
  const notesListEl = $('clienteNotesList')
  const apptsListEl = $('clienteApptsList')

  const addNoteForm = $('clienteAddNoteForm')
  const noteStatus = $('clienteNoteStatus')
  const addApptForm = $('clienteAddApptForm')
  const apptStatus = $('clienteApptStatus')

  const editModalEl = $('clienteEditModal')
  const editForm = $('clienteEditForm')
  const editError = $('clienteEditError')

  if (editModalEl && editModalEl.parentElement !== document.body) {
    document.body.appendChild(editModalEl)
  }
  const editModal = editModalEl && window.bootstrap?.Modal ? new window.bootstrap.Modal(editModalEl) : null

  let selectedClient = null

  const setText = (el, value, fallback = '—') => {
    if (!el) return
    const v = String(value ?? '').trim()
    el.textContent = v || fallback
  }

  const setStatus = (el, msg, type) => {
    if (!el) return
    const text = String(msg || '').trim()
    const useAlert = el.dataset?.statusUi === 'alert'

    if (useAlert) {
      el.textContent = text
      el.classList.remove('alert-danger', 'alert-success', 'alert-secondary', 'd-none')
      if (!text) {
        el.classList.add('d-none')
        return
      }
      if (type === 'error') el.classList.add('alert-danger')
      else if (type === 'success') el.classList.add('alert-success')
      else el.classList.add('alert-secondary')
      return
    }

    el.textContent = text
    el.classList.remove('text-danger', 'text-success', 'text-muted')
    if (!text) return
    if (type === 'error') el.classList.add('text-danger')
    else if (type === 'success') el.classList.add('text-success')
    else el.classList.add('text-muted')
  }

  const humanizeError = (code) => {
    const value = String(code || '').trim()
    if (!value) return ''
    const map = {
      cliente_ya_existe: 'El cliente ya existe (misma identificación).',
      id_type_requerido: 'Selecciona Cédula o Pasaporte.',
      id_type_invalido: 'Tipo de identificación inválido.',
      id_number_requerido: 'Número de identificación requerido.',
      full_name_requerido: 'Nombre requerido.',
    }
    return map[value] || value
  }

  const fmtDate = (iso) => {
    if (!iso) return ''
    const d = new Date(iso)
    if (isNaN(d.getTime())) return String(iso)
    return d.toLocaleString('es-ES')
  }

  const api = (path) => `/w/${encodeURIComponent(slug)}/api${path}`

  const renderClientItem = (client) => {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'list-group-item list-group-item-action'
    btn.dataset.clientId = client.id
    btn.innerHTML = `
          <div class="d-flex justify-content-between align-items-start gap-2">
        <div style="min-width:0;">
          <div class="fw-semibold text-truncate">${escapeHtml(client.full_name || '')}</div>
          <div class="small text-muted text-truncate">${escapeHtml(client.phone || client.email || client.id_number || '')}</div>
        </div>
        <span class="badge text-bg-light">${client.id}</span>
      </div>
    `
    btn.addEventListener('click', () => selectClient(client.id))
    return btn
  }

  const escapeHtml = (value) =>
    String(value || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;')

  const loadClients = async () => {
    if (!listEl) return
    listEl.innerHTML = ''
    setText(hintEl, 'Cargando...', '')
    const q = (searchInput?.value || '').trim()
    const url = new URL(api('/clientes'), window.location.origin)
    if (q) url.searchParams.set('q', q)
    try {
      const res = await fetch(url.toString(), { headers: { Accept: 'application/json' } })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error || `Error ${res.status}`)
      const items = Array.isArray(data.clients) ? data.clients : []
      if (!items.length) {
        setText(hintEl, q ? 'Sin resultados.' : 'Sin clientes aún.', '')
        return
      }
      setText(hintEl, `${items.length} cliente(s)`, '')
      items.forEach((c) => listEl.appendChild(renderClientItem(c)))
    } catch (err) {
      setText(hintEl, err?.message || 'No se pudo cargar', '')
    }
  }

  const setSelectedInList = (clientId) => {
    document.querySelectorAll('#clientesList .list-group-item').forEach((el) => {
      el.classList.toggle('active', el.dataset.clientId === String(clientId))
    })
  }

  const renderNotes = (notes) => {
    if (!notesListEl) return
    notesListEl.innerHTML = ''
    const items = Array.isArray(notes) ? notes : []
    if (!items.length) {
      notesListEl.innerHTML = '<div class="small text-muted">Sin notas.</div>'
      return
    }
    items.forEach((n) => {
      const div = document.createElement('div')
      div.className = 'border rounded-3 p-2 mb-2'
      div.innerHTML = `
        <div class="small text-muted mb-1">${escapeHtml(fmtDate(n.created_at))}</div>
        <div>${escapeHtml(n.body)}</div>
      `
      notesListEl.appendChild(div)
    })
  }

  const renderAppts = (appts) => {
    if (!apptsListEl) return
    apptsListEl.innerHTML = ''
    const items = Array.isArray(appts) ? appts : []
    if (!items.length) {
      apptsListEl.innerHTML = '<div class="small text-muted">Sin citas asociadas.</div>'
      return
    }
    items.forEach((a) => {
      const div = document.createElement('div')
      div.className = 'border rounded-3 p-2 mb-2'
      div.innerHTML = `
        <div class="d-flex justify-content-between gap-2">
          <div class="fw-semibold">${escapeHtml(a.title || '')}</div>
          <span class="badge text-bg-light">${escapeHtml(a.status || '')}</span>
        </div>
        <div class="small text-muted">${escapeHtml(fmtDate(a.start_time))} → ${escapeHtml(fmtDate(a.end_time))}</div>
        ${a.description ? `<div class="small mt-1">${escapeHtml(a.description)}</div>` : ''}
      `
      apptsListEl.appendChild(div)
    })
  }

  const showDetail = (data) => {
    selectedClient = data?.client || null
    const client = selectedClient
    editBtn && (editBtn.disabled = !client)
    if (!client) {
      detailBody && (detailBody.style.display = 'none')
      emptyHint && (emptyHint.style.display = '')
      setText(detailName, 'Selecciona un cliente', '')
      setText(detailMeta, '', '')
      return
    }
    emptyHint && (emptyHint.style.display = 'none')
    detailBody && (detailBody.style.display = '')
    setText(detailName, client.full_name, '')
    setText(detailMeta, `ID ${client.id} · Actualizado ${fmtDate(client.updated_at)}`, '')

    setText(phoneEl, client.phone)
    setText(emailEl, client.email)
    const idType = String(client.id_type || '').trim()
    const idNumber = String(client.id_number || '').trim()
    const idText = idNumber ? (idType ? `${idType}: ${idNumber}` : idNumber) : ''
    setText(identificationEl, idText)
    setText(addressEl, client.address)
    notesEl && (notesEl.textContent = client.notes || '—')

    renderNotes(data.notes)
    renderAppts(data.appointments)
  }

  const selectClient = async (clientId) => {
    setSelectedInList(clientId)
    setStatus(noteStatus, '', null)
    setStatus(apptStatus, '', null)
    try {
      const res = await fetch(api(`/clientes/${clientId}`), { headers: { Accept: 'application/json' } })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error || `Error ${res.status}`)
      showDetail(data)
    } catch (err) {
      showDetail(null)
      setText(detailName, err?.message || 'No se pudo cargar', '')
    }
  }

  createForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    setStatus(createStatus, '', null)
    const form = new FormData(createForm)
    const payload = Object.fromEntries(form.entries())
    try {
      const res = await fetch(api('/clientes'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const code = data.error || `Error ${res.status}`
        setStatus(createStatus, humanizeError(code), 'error')
        if (data.error === 'cliente_ya_existe' && data.existing_client_id) {
          await loadClients()
          await selectClient(data.existing_client_id)
        }
        return
      }
      setStatus(createStatus, 'Cliente guardado.', 'success')
      createForm.reset()
      await loadClients()
      if (data.client?.id) await selectClient(data.client.id)
    } catch (err) {
      setStatus(createStatus, err?.message || 'No se pudo guardar', 'error')
    }
  })

  refreshBtn?.addEventListener('click', () => void loadClients())
  searchInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      void loadClients()
    }
  })

  addNoteForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    if (!selectedClient?.id) return
    setStatus(noteStatus, '', null)
    const body = String(new FormData(addNoteForm).get('body') || '').trim()
    if (!body) {
      setStatus(noteStatus, 'Escribe una nota primero.', 'error')
      return
    }
    try {
      const res = await fetch(api(`/clientes/${selectedClient.id}/notas`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error || `Error ${res.status}`)
      addNoteForm.reset()
      setStatus(noteStatus, 'Nota guardada.', 'success')
      await selectClient(selectedClient.id)
    } catch (err) {
      setStatus(noteStatus, err?.message || 'No se pudo guardar', 'error')
    }
  })

  addApptForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    if (!selectedClient?.id) return
    setStatus(apptStatus, '', null)

    const form = new FormData(addApptForm)
    const payload = Object.fromEntries(form.entries())
    payload.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone

    const toIso = (v) => {
      if (!v) return ''
      const d = new Date(v)
      if (isNaN(d.getTime())) return v
      const pad = (n) => String(n).padStart(2, '0')
      const off = -d.getTimezoneOffset()
      const sign = off >= 0 ? '+' : '-'
      const abs = Math.abs(off)
      const hh = pad(Math.floor(abs / 60))
      const mm = pad(abs % 60)
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(
        d.getMinutes(),
      )}:00${sign}${hh}:${mm}`
    }

    payload.start_time = toIso(payload.start_time)
    payload.end_time = toIso(payload.end_time)

    try {
      const res = await fetch(api(`/clientes/${selectedClient.id}/citas`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error || `Error ${res.status}`)
      setStatus(apptStatus, 'Cita creada. Abre Calendario para verla.', 'success')
      addApptForm.reset()
      await selectClient(selectedClient.id)
    } catch (err) {
      setStatus(apptStatus, err?.message || 'No se pudo crear', 'error')
    }
  })

  const fillEditForm = (client) => {
    if (!editForm || !client) return
    editForm.full_name.value = client.full_name || ''
    editForm.phone.value = client.phone || ''
    editForm.email.value = client.email || ''
    if (editForm.id_type) editForm.id_type.value = client.id_type || ''
    if (editForm.id_number) editForm.id_number.value = client.id_number || ''
    editForm.address.value = client.address || ''
    editForm.notes.value = client.notes || ''
  }

  const setEditError = (msg) => {
    if (!editError) return
    const text = String(msg || '').trim()
    if (!text) {
      editError.classList.add('d-none')
      editError.textContent = ''
      return
    }
    editError.textContent = text
    editError.classList.remove('d-none')
  }

  editBtn?.addEventListener('click', () => {
    if (!selectedClient) return
    setEditError('')
    fillEditForm(selectedClient)
    if (editModal) editModal.show()
  })

  editForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    if (!selectedClient?.id) return
    setEditError('')
    const payload = Object.fromEntries(new FormData(editForm).entries())
    try {
      const res = await fetch(api(`/clientes/${selectedClient.id}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error || `Error ${res.status}`)
      editModal?.hide()
      await loadClients()
      await selectClient(selectedClient.id)
    } catch (err) {
      setEditError(err?.message || 'No se pudo guardar')
    }
  })

  document.addEventListener('DOMContentLoaded', () => void loadClients())
})()
