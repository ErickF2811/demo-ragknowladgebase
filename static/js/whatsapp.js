(() => {
  // Sin polling automático: solo llamamos a Evolution cuando el usuario pulsa el botón.

  const getEls = () => ({
    panel: document.getElementById('whatsappPanel'),
    btn: document.getElementById('whatsappFetchQrBtn'),
    refreshBtn: document.getElementById('whatsappRefreshStatusBtn'),
    logoutBtn: document.getElementById('whatsappLogoutBtn'),
    logoutModal: document.getElementById('whatsappLogoutModal'),
    logoutConfirmBtn: document.getElementById('whatsappLogoutConfirmBtn'),
    logoutError: document.getElementById('whatsappLogoutError'),
    img: document.getElementById('whatsappQrImg'),
    loading: document.getElementById('whatsappQrLoading'),
    placeholder: document.getElementById('whatsappQrPlaceholder'),
    status: document.getElementById('whatsappStatus'),
    instance: document.getElementById('whatsappInstanceName'),
    details: document.getElementById('whatsappDetails'),
    lastCheck: document.getElementById('whatsappLastCheck'),
    qrCard: document.getElementById('whatsappQrCard'),
    connectedCard: document.getElementById('whatsappConnectedCard'),
    connInfo: document.getElementById('whatsappConnectionInfo'),
    rawStatus: document.getElementById('whatsappRawStatus'),
  })

  const setStatus = (text, type) => {
    const { status } = getEls()
    if (!status) return
    status.textContent = text || ''
    status.classList.remove('text-muted', 'text-danger', 'text-success')
    if (!text) return
    if (type === 'error') status.classList.add('text-danger')
    else if (type === 'success') status.classList.add('text-success')
    else status.classList.add('text-muted')
  }

  const setDetails = (text) => {
    const { details } = getEls()
    if (!details) return
    const value = String(text || '').trim()
    if (!value) {
      details.style.display = 'none'
      details.textContent = ''
      return
    }
    details.textContent = value
    details.style.display = 'block'
  }

  const setLastCheck = (text) => {
    const { lastCheck } = getEls()
    if (!lastCheck) return
    const value = String(text || '').trim()
    if (!value) {
      lastCheck.style.display = 'none'
      lastCheck.textContent = ''
      return
    }
    lastCheck.textContent = value
    lastCheck.style.display = 'block'
  }

  const showConnectedPanel = (show) => {
    const { qrCard, connectedCard, loading, img, placeholder } = getEls()
    if (show) {
      if (qrCard) {
        qrCard.classList.remove('d-flex')
        qrCard.style.display = 'none'
        qrCard.setAttribute('hidden', 'hidden')
      }
      if (connectedCard) {
        connectedCard.style.display = 'block'
        connectedCard.removeAttribute('hidden')
      }
      if (loading) loading.style.display = 'none'
      if (img) img.style.display = 'none'
      if (placeholder) placeholder.style.display = 'none'
      return
    }
    if (connectedCard) {
      connectedCard.style.display = 'none'
      connectedCard.setAttribute('hidden', 'hidden')
    }
    if (qrCard) {
      qrCard.classList.add('d-flex')
      qrCard.style.display = 'flex'
      qrCard.removeAttribute('hidden')
    }
  }

  let connectedMode = false
  const syncActionButton = () => {
    const { btn, logoutBtn } = getEls()
    if (!btn) return
    if (connectedMode) {
      btn.style.display = 'none'
      if (logoutBtn) logoutBtn.style.display = ''
    } else {
      btn.style.display = ''
      btn.textContent = 'Generar QR'
      btn.classList.remove('btn-outline-secondary')
      btn.classList.add('btn-primary')
      if (logoutBtn) logoutBtn.style.display = 'none'
    }
  }

  const setQr = (dataUrl) => {
    const { img, placeholder } = getEls()
    if (!img || !placeholder) return
    if (dataUrl) {
      img.src = dataUrl
      img.style.display = 'block'
      placeholder.style.display = 'none'
    } else {
      img.removeAttribute('src')
      img.style.display = 'none'
      placeholder.style.display = 'block'
    }
  }

  const setLoading = (loading) => {
    const { loading: loadingEl, img, placeholder } = getEls()
    if (!loadingEl || !img || !placeholder) return
    if (loading) {
      loadingEl.style.display = 'block'
      img.style.display = 'none'
      placeholder.style.display = 'none'
    } else {
      loadingEl.style.display = 'none'
      // no decidimos aquí si hay QR o placeholder; lo controlan setQr/showConnectedPanel
    }
  }

  let pollTimer = null

  const stopPolling = () => {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = null
  }

  const checkStatus = async () => {
    const { panel } = getEls()
    const slug = panel?.getAttribute('data-workspace-slug')
    if (!slug) return { ok: false }

    try {
      const res = await fetch(`/w/${encodeURIComponent(slug)}/api/whatsapp/status`, {
        headers: { Accept: 'application/json' },
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data.ok === false) return { ok: false, data }

      setLastCheck(`Última validación: ${new Date().toLocaleString()}`)

      const stateNormalized = String(data.state || '').trim().toLowerCase()
      const isConnected = data.connected === true || stateNormalized === 'open'

      if (isConnected) {
         connectedMode = true
         syncActionButton()
         showConnectedPanel(true)
         setQr(null)
        const state = data.state ? ` (${data.state})` : ''
        setStatus(`WhatsApp conectado${state}.`, 'success')

        const detailParts = []
        if (data.details && typeof data.details === 'object') {
          const candidates = [
            ['number', 'Número'],
            ['phone', 'Teléfono'],
            ['profileName', 'Perfil'],
            ['profile_name', 'Perfil'],
            ['pushName', 'Nombre'],
            ['push_name', 'Nombre'],
            ['jid', 'JID'],
          ]
          candidates.forEach(([k, label]) => {
            const v = data.details?.[k]
            if (v !== undefined && v !== null && String(v).trim()) {
              detailParts.push(`${label}: ${String(v).trim()}`)
            }
          })
        }
        setDetails(detailParts.join(' · '))
        const { connInfo, rawStatus } = getEls()
        if (connInfo) connInfo.textContent = detailParts.length ? detailParts.join(' · ') : 'Conectado (sin detalles adicionales).'
         if (rawStatus) rawStatus.textContent = JSON.stringify(data, null, 2)

         // RabbitMQ se configura en `instance/create` (backend), no desde el frontend.
       } else if (data.connected === false) {
        connectedMode = false
        syncActionButton()
        showConnectedPanel(false)
        setDetails('')
        const state = data.state ? `Estado: ${data.state}. ` : ''
        setStatus(`${state}Escanea el QR para vincular.`, null)
        const { connInfo, rawStatus } = getEls()
        if (connInfo) connInfo.textContent = 'Aún no vinculado. Genera un QR para enlazar.'
        if (rawStatus) rawStatus.textContent = JSON.stringify(data, null, 2)
      } else if (data.state) {
        connectedMode = false
        syncActionButton()
        showConnectedPanel(false)
        setStatus(`Estado: ${data.state}`, null)
        const { rawStatus } = getEls()
        if (rawStatus) rawStatus.textContent = JSON.stringify(data, null, 2)
      }
      return { ok: true, connected: isConnected, state: data.state, data }
    } catch (_) {
      // silencioso: el polling no debe molestar
      return { ok: false }
    }
  }

  const fetchQr = async () => {
    const { panel, btn, instance } = getEls()
    const slug = panel?.getAttribute('data-workspace-slug')
    if (!slug) {
      setStatus('Selecciona un workspace para generar el QR.', 'error')
      return
    }

    // Primero valida estado; si ya está conectado no generamos nuevo QR.
    await checkStatus()
    if (connectedMode) return

    btn && (btn.disabled = true)
    setStatus('Generando QR en Evolution API...', null)
    setDetails('')
    showConnectedPanel(false)
    setLoading(true)
    setQr(null)

    try {
      const res = await fetch(`/w/${encodeURIComponent(slug)}/api/whatsapp/qr`, {
        headers: { Accept: 'application/json' },
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data.ok === false) {
        throw new Error(data.error || `Error ${res.status}`)
      }
      if (instance && data.instance_name) instance.textContent = data.instance_name
      if (!data.qr_data_url) throw new Error('Respuesta sin QR')

      setLoading(false)
      setQr(data.qr_data_url)
      setStatus('QR listo. Escanéalo desde WhatsApp → Dispositivos vinculados.', 'success')
    } catch (err) {
      setLoading(false)
      setStatus(err?.message || 'No se pudo obtener el QR', 'error')
      setDetails('')
      setQr(null)
      stopPolling()
    } finally {
      setLoading(false)
      btn && (btn.disabled = false)
    }
  }

  const initWhatsApp = () => {
    const { btn, refreshBtn, logoutBtn } = getEls()
    if (!btn) return
    // Limpieza por si quedo un backdrop pegado por errores previos.
    document.body.classList.remove('modal-open')
    document.body.style.removeProperty('padding-right')
    document.querySelectorAll('.modal-backdrop').forEach((el) => el.remove())
    syncActionButton()

    // GET-only: al cargar la pestaña, consultamos estado una sola vez (sin crear QR ni reconectar).
    refreshBtn?.addEventListener('click', async () => {
      refreshBtn.disabled = true
      try {
        await checkStatus()
      } finally {
        refreshBtn.disabled = false
      }
    })
    void checkStatus()
    btn.addEventListener('click', async () => {
      btn.disabled = true
      try {
        const status = await checkStatus()
        if (status?.connected) return
        await fetchQr()
      } finally {
        btn.disabled = false
      }
    })

    const logoutModalEl = getEls().logoutModal
    const logoutConfirmBtn = getEls().logoutConfirmBtn
    const logoutError = getEls().logoutError
    if (logoutModalEl && logoutModalEl.parentElement !== document.body) {
      document.body.appendChild(logoutModalEl)
    }
    const logoutModal =
      logoutModalEl && window.bootstrap?.Modal ? new window.bootstrap.Modal(logoutModalEl) : null

    const setLogoutError = (message) => {
      if (!logoutError) return
      const text = String(message || '').trim()
      if (!text) {
        logoutError.classList.add('d-none')
        logoutError.textContent = ''
        return
      }
      logoutError.textContent = text
      logoutError.classList.remove('d-none')
    }

    const cleanupModalArtifacts = () => {
      document.body.classList.remove('modal-open')
      document.body.style.removeProperty('padding-right')
      document.querySelectorAll('.modal-backdrop').forEach((el) => el.remove())
      if (logoutModalEl) {
        logoutModalEl.classList.remove('show')
        logoutModalEl.style.display = 'none'
        logoutModalEl.setAttribute('aria-hidden', 'true')
      }
    }

    logoutBtn?.addEventListener('click', () => {
      setLogoutError('')
      if (logoutModal) {
        logoutModal.show()
        return
      }
      cleanupModalArtifacts()
      const ok = window.confirm('cerrar session whatapp')
      if (ok) logoutConfirmBtn?.click()
    })

    logoutModalEl
      ?.querySelectorAll('[data-bs-dismiss=\"modal\"], .btn-close')
      .forEach((el) => el.addEventListener('click', cleanupModalArtifacts))

    logoutModalEl?.addEventListener('hidden.bs.modal', () => {
      setLogoutError('')
      cleanupModalArtifacts()
    })

    logoutConfirmBtn?.addEventListener('click', async () => {
      const { panel } = getEls()
      const slug = panel?.getAttribute('data-workspace-slug')
      if (!slug) return
      logoutConfirmBtn.disabled = true
      setLogoutError('')
      setStatus('Cerrando sesión en Evolution API...', null)
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 20000)
        const res = await fetch(`/w/${encodeURIComponent(slug)}/api/whatsapp/logout`, {
          method: 'POST',
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        }).finally(() => clearTimeout(timeoutId))
        const data = await res.json().catch(() => ({}))
        if (!res.ok || data.ok === false) throw new Error(data.error || `Error ${res.status}`)
        logoutModal?.hide()
        cleanupModalArtifacts()
        setStatus('Sesión cerrada. Genera un nuevo QR para volver a vincular.', 'success')
        connectedMode = false
        syncActionButton()
        showConnectedPanel(false)
        stopPolling()
      } catch (err) {
        const message =
          err?.name === 'AbortError'
            ? 'Tiempo de espera agotado cerrando sesión. Intenta de nuevo.'
            : err?.message || 'No se pudo cerrar sesión'
        setLogoutError(message)
      } finally {
        logoutConfirmBtn.disabled = false
      }
    })

    window.addEventListener('beforeunload', () => stopPolling())
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWhatsApp)
  } else {
    initWhatsApp()
  }
})()
