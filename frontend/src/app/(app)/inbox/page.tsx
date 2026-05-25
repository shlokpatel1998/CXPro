'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'

interface InboxItem {
  id: string
  user_id: string
  project_id: string
  source_event_type: string
  source_resource_id: string | null
  source_resource_type: string | null
  title: string
  description: string | null
  item_type: 'ai_draft' | 'ai_refusal' | 'other'
  action_state: 'pending' | 'acted' | 'dismissed'
  test_procedure_instance_id: string | null
  document_id: string | null
  agent_run_id: string | null
  metadata: Record<string, unknown> | null
  priority: number
  bucket_date: string
  created_at: string
  acted_at: string | null
}

interface Project {
  id: string
  name: string
}

export default function InboxPage() {
  const [user, setUser] = useState<{ id: string; email?: string } | null>(null)
  const [inboxItems, setInboxItems] = useState<InboxItem[]>([])
  const [projects, setProjects] = useState<Map<string, Project>>(new Map())
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  const loadInboxItems = async () => {
    try {
      // Load pending inbox items for the current user
      const { data: items, error } = await supabase
        .from('inbox_items')
        .select('*')
        .eq('action_state', 'pending')
        .order('priority', { ascending: false })
        .order('created_at', { ascending: false })

      if (error) {
        console.error('Error loading inbox items:', error)
        return
      }

      setInboxItems(items || [])

      // Load project names for the items
      if (items && items.length > 0) {
        const projectIds = [...new Set(items.map(item => item.project_id))]
        const { data: projectsData } = await supabase
          .from('projects')
          .select('id, name')
          .in('id', projectIds)

        if (projectsData) {
          const projectMap = new Map(projectsData.map(p => [p.id, p]))
          setProjects(projectMap)
        }
      }
    } catch (error) {
      console.error('Error loading inbox:', error)
    }
  }

  useEffect(() => {
    const getUser = async () => {
      const { data: { session } } = await supabase.auth.getSession()
      
      if (!session?.user) {
        router.push('/auth')
        return
      }

      setUser(session.user)
      await loadInboxItems()
      setLoading(false)
    }

    getUser()
  }, [router])

  // Set up Realtime subscription for inbox updates
  useEffect(() => {
    if (!user) return

    const channel = supabase
      .channel(`inbox_${user.id}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'inbox_items',
          filter: `user_id=eq.${user.id}`
        },
        (payload) => {
          console.log('Inbox update:', payload)
          
          if (payload.eventType === 'INSERT') {
            // Add new item if it's pending
            if (payload.new && (payload.new as InboxItem).action_state === 'pending') {
              setInboxItems(prev => [payload.new as InboxItem, ...prev])
            }
          } else if (payload.eventType === 'UPDATE') {
            // Update existing item
            const updated = payload.new as InboxItem
            if (updated.action_state !== 'pending') {
              // Remove from inbox if no longer pending
              setInboxItems(prev => prev.filter(item => item.id !== updated.id))
            } else {
              // Update the item
              setInboxItems(prev => prev.map(item => 
                item.id === updated.id ? updated : item
              ))
            }
          } else if (payload.eventType === 'DELETE') {
            // Remove deleted item
            setInboxItems(prev => prev.filter(item => item.id !== (payload.old as InboxItem).id))
          }
        }
      )
      .subscribe()

    return () => {
      channel.unsubscribe()
    }
  }, [user])

  const handleReviewDraft = (item: InboxItem) => {
    if (item.test_procedure_instance_id) {
      // Navigate to the entity detail page for the test procedure
      router.push(`/entity/${item.test_procedure_instance_id}`)
    }
  }

  const handleUploadMoreDocs = (item: InboxItem) => {
    if (item.project_id) {
      // Navigate to project page to upload more documents
      router.push(`/project/${item.project_id}`)
    }
  }

  const getAiBadge = () => (
    <span className="bp-ai-badge">⚡</span>
  )

  if (loading) {
    return (
      <div className="bp-screen">
        <div className="bp-loading">Loading inbox...</div>
      </div>
    )
  }

  return (
    <div className="bp-screen">
      <div className="bp-page-head">
        <div>
          <div className="bp-eyebrow">— INBOX</div>
          <h1 className="bp-h1">Your action items</h1>
          <div className="bp-subtle">Across all projects</div>
        </div>
      </div>

      <div className="bp-inbox-content">
        {inboxItems.length === 0 ? (
          <div className="bp-empty-state">
            <div className="bp-empty-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
            </div>
            <h3 className="bp-empty-title">Nothing needs your attention</h3>
            <p className="bp-empty-text">Upload a document to get started.</p>
          </div>
        ) : (
          <div className="bp-inbox-items">
            {/* Daily bucket header */}
            <div className="bp-bucket-header">
              Today&apos;s Items
            </div>
            
            {/* Inbox items */}
            {inboxItems.map((item) => {
              const project = projects.get(item.project_id)
              const isRefusal = item.item_type === 'ai_refusal'
              
              return (
                <div
                  key={item.id}
                  className={`bp-inbox-card ${isRefusal ? 'bp-refusal' : ''}`}
                >
                  <div className="bp-inbox-card-body">
                    <div className="bp-inbox-card-content">
                      {item.item_type === 'ai_draft' && getAiBadge()}
                      <div className="bp-inbox-card-main">
                        <div className="bp-inbox-card-header">
                          <h3 className="bp-inbox-card-title">{item.title}</h3>
                          {item.item_type === 'ai_draft' && (
                            <span className="bp-status-badge bp-status-info">
                              AI Draft
                            </span>
                          )}
                          {item.item_type === 'ai_refusal' && (
                            <span className="bp-status-badge bp-status-warning">
                              Needs Info
                            </span>
                          )}
                        </div>
                        
                        {item.description && (
                          <p className="bp-inbox-card-desc">{item.description}</p>
                        )}
                        
                        <div className="bp-inbox-card-meta">
                          {project && (
                            <span>Project: {project.name}</span>
                          )}
                          {(() => {
                            const assetTag = item.metadata?.['asset_tag']
                            if (assetTag) {
                              return (
                                <>
                                  <span className="bp-dot"/>
                                  <span>Asset: {String(assetTag)}</span>
                                </>
                              )
                            }
                            return null
                          })()}
                          {(() => {
                            const documentName = item.metadata?.['document_name']
                            if (documentName) {
                              return (
                                <>
                                  <span className="bp-dot"/>
                                  <span>Source: {String(documentName)}</span>
                                </>
                              )
                            }
                            return null
                          })()}
                        </div>
                      </div>
                    </div>
                    
                    <div className="bp-inbox-card-action">
                      {isRefusal ? (
                        <button
                          onClick={() => handleUploadMoreDocs(item)}
                          className="bp-btn-warning"
                        >
                          Upload more docs
                        </button>
                      ) : (
                        <button
                          onClick={() => handleReviewDraft(item)}
                          className="bp-btn-primary"
                        >
                          Review draft
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <style jsx>{`
        .bp-screen {
          padding: 32px;
          max-width: 1200px;
          margin: 0 auto;
        }

        .bp-page-head {
          margin-bottom: 48px;
        }

        .bp-eyebrow {
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.15em;
          color: var(--bp-text-secondary);
          margin-bottom: 12px;
        }

        .bp-h1 {
          font-size: 32px;
          font-weight: 600;
          margin: 0;
          color: var(--bp-text);
        }

        .bp-subtle {
          font-size: 14px;
          color: var(--bp-text-tertiary);
          margin-top: 8px;
        }

        .bp-loading {
          text-align: center;
          padding: 60px 20px;
          color: var(--bp-text-secondary);
        }

        .bp-empty-state {
          text-align: center;
          padding: 80px 20px;
          background: var(--bp-surface);
          border: 1px solid var(--bp-border);
          border-radius: 8px;
        }

        .bp-empty-icon {
          width: 48px;
          height: 48px;
          margin: 0 auto 24px;
          color: var(--bp-text-tertiary);
        }

        .bp-empty-title {
          font-size: 18px;
          font-weight: 600;
          color: var(--bp-text);
          margin-bottom: 8px;
        }

        .bp-empty-text {
          color: var(--bp-text-secondary);
          margin: 0;
        }

        .bp-inbox-items {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .bp-bucket-header {
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: var(--bp-text-tertiary);
          margin-bottom: 8px;
        }

        .bp-inbox-card {
          background: var(--bp-surface);
          border: 1px solid var(--bp-border);
          border-radius: 8px;
          transition: all 0.2s;
        }

        .bp-inbox-card:hover {
          border-color: var(--bp-accent);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }

        .bp-inbox-card.bp-refusal {
          border-left: 3px solid var(--bp-warning);
        }

        .bp-inbox-card-body {
          padding: 20px;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 20px;
        }

        .bp-inbox-card-content {
          flex: 1;
          display: flex;
          gap: 12px;
        }

        .bp-ai-badge {
          font-size: 20px;
          color: var(--bp-accent);
        }

        .bp-inbox-card-main {
          flex: 1;
        }

        .bp-inbox-card-header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 8px;
        }

        .bp-inbox-card-title {
          font-size: 16px;
          font-weight: 600;
          color: var(--bp-text);
          margin: 0;
        }

        .bp-status-badge {
          display: inline-block;
          padding: 2px 8px;
          font-size: 11px;
          font-weight: 500;
          border-radius: 12px;
          text-transform: uppercase;
          letter-spacing: 0.02em;
        }

        .bp-status-info {
          background: var(--bp-info-bg);
          color: var(--bp-info-text);
        }

        .bp-status-warning {
          background: var(--bp-warning-bg);
          color: var(--bp-warning-text);
        }

        .bp-inbox-card-desc {
          color: var(--bp-text-secondary);
          margin: 0 0 12px 0;
          font-size: 14px;
        }

        .bp-inbox-card-meta {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          color: var(--bp-text-tertiary);
        }

        .bp-dot {
          width: 3px;
          height: 3px;
          background: var(--bp-text-tertiary);
          border-radius: 50%;
        }

        .bp-inbox-card-action {
          flex-shrink: 0;
        }

        .bp-btn-primary, .bp-btn-warning {
          padding: 8px 16px;
          font-size: 14px;
          font-weight: 500;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .bp-btn-primary {
          background: var(--bp-accent);
          color: white;
        }

        .bp-btn-primary:hover {
          background: var(--bp-accent-hover);
          transform: translateY(-1px);
        }

        .bp-btn-warning {
          background: var(--bp-warning);
          color: white;
        }

        .bp-btn-warning:hover {
          background: var(--bp-warning-hover);
          transform: translateY(-1px);
        }
      `}</style>
    </div>
  )
}