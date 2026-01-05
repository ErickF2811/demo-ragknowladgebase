import './style.css'
import { Clerk } from '@clerk/clerk-js'

const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
const panelUrl = import.meta.env.VITE_PANEL_URL ?? 'http://localhost:5000'

const renderSignedOut = (appElement, clerk) => {
  appElement.innerHTML = `
    <div class="auth-shell">
      <h1 class="app-title">Bienvenido</h1>
      <p class="app-copy">Por favor inicia sesión para continuar.</p>
      <div id="sign-in"></div>
    </div>
  `

  const signInDiv = document.getElementById('sign-in')
  if (signInDiv) {
    clerk.mountSignIn(signInDiv)
  }
}

const renderSignedIn = async (appElement, clerk) => {
  const user = clerk?.user
  const email =
    user?.primaryEmailAddress?.emailAddress || user?.emailAddresses?.[0]?.emailAddress
  const fullName =
    user?.fullName || `${user?.firstName ?? ''} ${user?.lastName ?? ''}`.trim()
  const clerkId = user?.id || null

  if (!email) {
    appElement.innerHTML = `
      <div class="auth-shell">
        <p class="app-error">Tu cuenta de Clerk no tiene un correo principal. Añádelo para continuar.</p>
      </div>`
    return
  }

  appElement.innerHTML = `
    <div class="auth-shell">
      <div class="spinner-border text-primary" role="status"></div>
      <p class="mt-3">Sincronizando sesión…</p>
    </div>
  `

  try {
    const token = await clerk?.session?.getToken?.()
    if (!token) {
      throw new Error('No se pudo obtener el token de Clerk (session.getToken).')
    }
    await fetch(`${panelUrl.replace(/\/$/, '')}/session/clerk`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ email, name: fullName, clerk_id: clerkId }),
      credentials: 'include',
    })
    window.location.href = panelUrl
  } catch (error) {
    console.error('No se pudo sincronizar la sesión con el panel', error)
    appElement.innerHTML = `
      <div class="auth-shell">
        <p class="app-error">No se pudo abrir el panel. Intenta de nuevo.</p>
        <button class="btn btn-primary mt-3" id="retryBtn">Reintentar</button>
      </div>
    `
    document.getElementById('retryBtn')?.addEventListener('click', () =>
      renderSignedIn(appElement, clerk)
    )
  }
}

async function bootstrapClerk() {
  const appElement = document.getElementById('app')

  if (!appElement) {
    throw new Error('No se encontró el elemento raíz #app.')
  }

  if (!clerkPubKey) {
    appElement.innerHTML =
      '<div class="auth-shell"><p class="app-error">Configura VITE_CLERK_PUBLISHABLE_KEY en clerk-javascript/.env</p></div>'
    throw new Error('Missing VITE_CLERK_PUBLISHABLE_KEY environment variable')
  }

  const clerk = new Clerk(clerkPubKey)
  await clerk.load()

  const render = () => {
    if (clerk.isSignedIn) {
      renderSignedIn(appElement, clerk)
    } else {
      renderSignedOut(appElement, clerk)
    }
  }

  render()
  clerk.addListener(render)
}

bootstrapClerk().catch((error) => {
  console.error('Error inicializando Clerk:', error)
  const appElement = document.getElementById('app')

  if (appElement) {
    appElement.innerHTML = `
      <div class="auth-shell">
        <p class="app-error">Ocurrió un error al cargar Clerk.</p>
        <pre class="app-error">${error.message}</pre>
      </div>
    `
  }
})
