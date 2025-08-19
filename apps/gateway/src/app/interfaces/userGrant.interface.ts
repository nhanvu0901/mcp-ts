export interface UserGrantInterface {
  access_token?: Token
  refresh_token?: Token
  id_token?: Token
  expires_in?: string
  refresh_expires_in?: string
  token_type?: string
  expired?: boolean
  session_state?: string
  scope?: string
}

export interface Token {
  token?: string
  clientId?: string
  content?: any
  isExpired(): boolean
  hasRole(roleName: string): boolean
  hasApplicationRole(appName: string, roleName: string): boolean
  hasRealmRole(roleName: string): boolean
}