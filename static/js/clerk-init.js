(() => {
  const body = document.body
  if (!body) return
  const publishableKey = body.getAttribute('data-clerk-key')
  const authSection = document.getElementById('clerk-auth-section')
  const signInEl = document.getElementById('clerk-sign-in')
  const userButtonEl = document.getElementById('clerk-user-button')
  const userNameEl = document.getElementById('clerk-user-name')
  const appContent = document.getElementById('app-shell-content')
  const roleEl = document.getElementById('clerk-role-pill')
  const logoutBtn = document.getElementById('clerk-logout-btn')

  const showApp = () => {
    authSection?.classList.add('hidden')
    appContent?.removeAttribute('hidden')
  }

  const showAuth = () => {
    appContent?.setAttribute('hidden', 'hidden')
    authSection?.classList.remove('hidden')
  }

  const renderClerkError = (message) => {
    showAuth()
    if (signInEl) {
      signInEl.innerHTML = `
        <div class="alert alert-warning text-start" role="alert">
          ${message}
        </div>
      `
    }
  }

  const updateUserName = (user) => {
    if (!userNameEl) return
    const email = user?.primaryEmailAddress?.emailAddress || user?.emailAddresses?.[0]?.emailAddress
    userNameEl.textContent = user?.fullName || email || 'Invitado'
  }

  const deriveRole = (user) => {
    const fromMetadata = user?.publicMetadata?.role
    const fromOrg = user?.organizationMemberships?.[0]?.role
    if (fromMetadata && String(fromMetadata).trim()) return fromMetadata
    if (fromOrg && String(fromOrg).trim()) return fromOrg
    return 'Miembro'
  }

  const updateRole = (user) => {
    if (!roleEl) return
    if (!user) {
      roleEl.textContent = 'Invitado'
      return
    }
    roleEl.textContent = deriveRole(user)
  }

  const syncSession = async (user) => {
    const email =
      user?.primaryEmailAddress?.emailAddress || user?.emailAddresses?.[0]?.emailAddress
    const name = user?.fullName || `${user?.firstName ?? ''} ${user?.lastName ?? ''}`.trim()
    const clerkId = user?.id || null
    const role = deriveRole(user)
    if (!email) return
    try {
      await fetch('/session/clerk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ email, name, clerk_id: clerkId, role }),
      })
    } catch (err) {
      console.error('No se pudo sincronizar la sesion con el backend', err)
    }
  }

  const clearBackendSession = async () => {
    try {
      await fetch('/session/clerk', {
        method: 'DELETE',
        headers: {
          'Accept': 'application/json',
        },
      })
    } catch (err) {
      console.error('No se pudo limpiar la sesion del backend', err)
    }
  }

  if (!publishableKey) {
    renderClerkError('Configura CLERK_PUBLISHABLE_KEY en el backend para habilitar el inicio de sesión.')
    return
  }

  const bootstrap = async () => {
    try {
      await window.Clerk.load({ publishableKey })
    } catch (error) {
      console.error('Error inicializando Clerk', error)
      const hint =
        'No se pudo cargar Clerk. Asegúrate de que el dominio (p. ej. http://localhost:5000) esté autorizado en el dashboard de Clerk.'
      renderClerkError(hint)
      return
    }

    const clerk = window.Clerk
    let signInMounted = false
    let userButtonMounted = false

    const mountSignIn = () => {
      if (!signInEl) return
      if (signInMounted) {
        clerk.unmountSignIn?.(signInEl)
      }
      clerk.mountSignIn(signInEl)
      signInMounted = true
    }

    const mountUserButton = () => {
      if (!userButtonEl) return
      if (userButtonMounted) {
        clerk.unmountUserButton?.(userButtonEl)
      }
      userButtonEl.innerHTML = ''
      clerk.mountUserButton(userButtonEl)
      userButtonMounted = true
    }

    const handleSignedIn = async () => {
      await syncSession(clerk.user)

      const backendEmailMeta = document.querySelector('meta[name="backend-user-email"]')
      const backendEmail = backendEmailMeta ? backendEmailMeta.getAttribute('content') : null

      if ((!backendEmail || backendEmail === '') && clerk.user) {
        // Backend no conocia la sesion. Ahora que hemos sincronizado, recargamos.
        window.location.reload()
        return
      }

      updateUserName(clerk.user)
      updateRole(clerk.user)
      mountUserButton()
      if (logoutBtn) {
        logoutBtn.removeAttribute('hidden')
        logoutBtn.onclick = async () => {
          try {
            await clerk.signOut()
          } finally {
            clearBackendSession()
          }
        }
      }
      showApp()
    }

    const handleSignedOut = () => {
      if (userNameEl) {
        userNameEl.textContent = 'Invitado'
      }
      updateRole(null)
      showAuth()
      clearBackendSession()
      if (logoutBtn) {
        logoutBtn.setAttribute('hidden', 'hidden')
        logoutBtn.onclick = null
      }
      mountSignIn()
    }

    if (clerk.session) {
      handleSignedIn()
    } else {
      handleSignedOut()
    }

    clerk.addListener(({ session }) => {
      if (session) {
        handleSignedIn()
      } else {
        handleSignedOut()
      }
    })
  }

  let bootstrapped = false
  const startClerk = () => {
    if (bootstrapped) return
    bootstrapped = true
    bootstrap()
  }

  if (window.Clerk) {
    startClerk()
  } else {
    window.addEventListener('load', startClerk, { once: true })
  }
})()
