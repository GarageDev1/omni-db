import { useForm } from 'react-hook-form'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'
import { useTranslation } from 'react-i18next'
import { useEffect, useState } from 'react'
import type { CasdoorConfig } from '@/types/auth'

export default function LoginPage() {
  const { register, handleSubmit } = useForm<{ username: string; password: string }>()
  const setAuth = useAuthStore(s => s.setAuth)
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [casdoor, setCasdoor] = useState<CasdoorConfig | null>(null)

  useEffect(() => {
    authApi.casdoorConfig()
      .then(setCasdoor)
      .catch(() => setCasdoor(null))
  }, [])

  const onSubmit = async (data: { username: string; password: string }) => {
    setLoading(true)
    setError('')
    try {
      const res = await authApi.login(data.username, data.password) as any
      localStorage.setItem('token', res.access_token)
      const profile = await authApi.profile() as any
      setAuth(profile, res.access_token)
      navigate('/')
    } catch (e: any) {
      localStorage.removeItem('token')
      console.error('login failed:', e)
      setError(e?.response ? t('auth.login_error') : t('auth.network_error'))
    } finally {
      setLoading(false)
    }
  }

  const startCasdoorLogin = () => {
    if (!casdoor?.enabled) return
    const redirectUri = casdoor.redirect_uri || `${window.location.origin}/auth/callback`
    const state = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`
    sessionStorage.setItem('casdoor_oauth_state', state)
    sessionStorage.setItem('casdoor_oauth_redirect_uri', redirectUri)
    const params = new URLSearchParams({
      client_id: casdoor.client_id,
      response_type: 'code',
      redirect_uri: redirectUri,
      scope: casdoor.scope || 'openid profile email',
      state,
    })
    window.location.assign(`${casdoor.endpoint.replace(/\/$/, '')}/login/oauth/authorize?${params}`)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm bg-white rounded-lg shadow p-8">
        <h1 className="text-2xl font-semibold mb-2">OntoPrompt</h1>
        <p className="text-gray-500 text-sm mb-6">本体知识工程平台</p>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">{t('auth.username')}</label>
            <input {...register('username', { required: true })} placeholder="用户名"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t('auth.password')}</label>
            <input {...register('password', { required: true })} type="password" placeholder="密码"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black" />
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button type="submit" disabled={loading}
            className="w-full bg-black text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50">
            {loading ? t('common.loading') : t('auth.login')}
          </button>
        </form>
        {casdoor?.enabled && (
          <>
            <div className="flex items-center gap-3 my-5">
              <div className="h-px flex-1 bg-gray-200" />
              <span className="text-xs text-gray-400">{t('auth.or')}</span>
              <div className="h-px flex-1 bg-gray-200" />
            </div>
            <button type="button" onClick={startCasdoorLogin}
              className="w-full border border-gray-300 rounded-lg py-2 text-sm font-medium hover:bg-gray-50">
              {t('auth.casdoor_login')}
            </button>
          </>
        )}
        <p className="mt-4 text-sm text-center text-gray-500">
          {t('auth.no_account')} <Link to="/register" className="text-black underline">{t('auth.register')}</Link>
        </p>
      </div>
    </div>
  )
}
