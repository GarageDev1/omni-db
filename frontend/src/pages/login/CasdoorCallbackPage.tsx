import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'

export default function CasdoorCallbackPage() {
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const { t } = useTranslation()
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function completeLogin() {
      const params = new URLSearchParams(window.location.search)
      const providerError = params.get('error')
      const code = params.get('code')
      const state = params.get('state')
      const expectedState = sessionStorage.getItem('casdoor_oauth_state')
      const redirectUri = sessionStorage.getItem('casdoor_oauth_redirect_uri') || `${window.location.origin}/auth/callback`

      if (providerError) {
        setError(providerError)
        return
      }
      if (!code) {
        setError(t('auth.casdoor_missing_code'))
        return
      }
      if (expectedState && state !== expectedState) {
        setError(t('auth.casdoor_state_error'))
        return
      }

      try {
        const token = await authApi.casdoorCallback({ code, state, redirect_uri: redirectUri })
        localStorage.setItem('token', token.access_token)
        const profile = await authApi.profile()
        if (cancelled) return
        sessionStorage.removeItem('casdoor_oauth_state')
        sessionStorage.removeItem('casdoor_oauth_redirect_uri')
        setAuth(profile, token.access_token)
        navigate('/', { replace: true })
      } catch (e: any) {
        if (!cancelled) setError(e?.detail || t('auth.casdoor_callback_error'))
      }
    }

    completeLogin()
    return () => {
      cancelled = true
    }
  }, [navigate, setAuth, t])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm bg-white rounded-lg shadow p-8">
        <h1 className="text-2xl font-semibold mb-2">{t('auth.casdoor_callback_title')}</h1>
        {error ? (
          <p className="text-sm text-red-500">{error}</p>
        ) : (
          <p className="text-sm text-gray-500">{t('common.loading')}</p>
        )}
      </div>
    </div>
  )
}
