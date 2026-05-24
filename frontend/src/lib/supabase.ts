import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!

export const supabase = createClient(supabaseUrl, supabaseKey)

// Database types
export interface User {
  id: string
  email: string
  full_name?: string
  created_at: string
  updated_at: string
}

export interface Org {
  id: string
  name: string
  slug: string
  created_at: string
  updated_at: string
}

export interface Membership {
  id: string
  user_id: string
  org_id: string
  role: 'OCA' | 'cx_engineer'
  created_at: string
}

export interface Project {
  id: string
  org_id: string
  name: string
  description?: string
  created_at: string
  updated_at: string
}

export interface DisciplineScope {
  id: string
  project_id: string
  name: string
  description?: string
  created_at: string
}

export interface Participation {
  id: string
  user_id: string
  project_id: string
  created_at: string
}

export interface Assignment {
  id: string
  user_id: string
  discipline_scope_id: string
  created_at: string
}