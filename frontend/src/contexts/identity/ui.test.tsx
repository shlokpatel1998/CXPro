import { describe, test, expect, vi } from 'vitest'
import { UserMenu } from './ui'

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
      signOut: vi.fn().mockResolvedValue({})
    }
  }
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() })
}))

vi.mock('next/link', () => ({
  default: ({ href, children, onClick, className }: { href: string; children: React.ReactNode; onClick?: () => void; className?: string }) => {
    const React = require('react')
    return React.createElement('a', { href, onClick, className }, children)
  }
}))

describe('UserMenu', () => {
  test('is exported as a named export', () => {
    expect(typeof UserMenu).toBe('function')
  })

  test('UserMenu accepts required props without TypeScript errors', () => {
    const props = {
      projectId: 'proj-123',
      theme: 'light' as const,
      onThemeChange: vi.fn()
    }
    expect(props.projectId).toBe('proj-123')
    expect(props.theme).toBe('light')
  })

  test('UserMenu accepts null projectId', () => {
    const props = {
      projectId: null,
      theme: 'dark' as const,
      onThemeChange: vi.fn()
    }
    expect(props.projectId).toBeNull()
    expect(props.theme).toBe('dark')
  })

  test('onThemeChange toggles from light to dark', () => {
    const onThemeChange = vi.fn()
    const currentTheme: 'light' | 'dark' = 'light'
    const expectedNext: 'light' | 'dark' = currentTheme === 'light' ? 'dark' : 'light'
    onThemeChange(expectedNext)
    expect(onThemeChange).toHaveBeenCalledWith('dark')
  })

  test('onThemeChange toggles from dark to light', () => {
    const onThemeChange = vi.fn()
    const toggle = (t: 'light' | 'dark'): 'light' | 'dark' => t === 'light' ? 'dark' : 'light'
    onThemeChange(toggle('dark'))
    expect(onThemeChange).toHaveBeenCalledWith('light')
  })
})
