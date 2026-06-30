export interface User {
  id: string
  username: string
  email: string
  role: 'admin' | 'editor' | 'viewer'
  display_name?: string | null
  avatar?: string | null
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface CasdoorConfig {
  enabled: boolean
  endpoint: string
  client_id: string
  redirect_uri: string
  scope: string
}
