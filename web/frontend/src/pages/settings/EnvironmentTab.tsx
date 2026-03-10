import { useEffect, useState, useCallback } from 'react'
import { api } from '../../api/client'
import LoadingSpinner from '../../components/LoadingSpinner'
import ErrorMessage from '../../components/ErrorMessage'

const SENSITIVE_KEYS = ['api_key', 'token', 'secret', 'password', 'key']

function isSensitiveKey(key: string): boolean {
  const lower = key.toLowerCase()
  return SENSITIVE_KEYS.some((s) => lower.includes(s))
}

export default function EnvEditor() {
  const [variables, setVariables] = useState<Record<string, string> | null>(null)
  const [editedVars, setEditedVars] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set())

  const loadEnv = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getEnv()
      setVariables(data.variables)
      setEditedVars(data.variables)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load env')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadEnv()
  }, [loadEnv])

  const handleChange = (key: string, value: string) => {
    setEditedVars((prev) => ({ ...prev, [key]: value }))
  }

  const toggleReveal = (key: string) => {
    setRevealedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveMessage(null)
    try {
      await api.updateEnv(editedVars)
      setVariables(editedVars)
      setSaveMessage({ type: 'success', text: 'Environment saved successfully' })
    } catch (e) {
      setSaveMessage({ type: 'error', text: e instanceof Error ? e.message : 'Failed to save env' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={loadEnv} />
  }

  const hasChanges = variables !== null && JSON.stringify(editedVars) !== JSON.stringify(variables)

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Environment Variables</h2>
            <p className="text-xs text-slate-400">API keys and secrets</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {hasChanges && (
            <span className="inline-flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-lg">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              Unsaved changes
            </span>
          )}
          <button
            onClick={() => {
              if (variables) setEditedVars(variables)
            }}
            disabled={!hasChanges}
            className="px-3.5 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg disabled:opacity-50 transition-colors"
          >
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className="px-3.5 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 flex items-center gap-2 shadow-sm transition-colors"
          >
            {saving && <LoadingSpinner size="sm" />}
            Save
          </button>
        </div>
      </div>
      <div className="p-5">
        {saveMessage && (
          <div className={`mb-4 px-3 py-2 rounded-lg text-sm border ${
            saveMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
              : 'bg-red-50 border-red-200 text-red-700'
          }`}>
            {saveMessage.text}
          </div>
        )}
        <div className="space-y-3">
          {Object.entries(editedVars).map(([key, value]) => {
            const sensitive = isSensitiveKey(key)
            const revealed = revealedKeys.has(key)
            return (
              <div key={key} className="flex items-center gap-3">
                <label className="w-56 text-sm font-medium text-slate-700 flex-shrink-0 font-mono bg-slate-50 border border-slate-200 px-3 py-2 rounded-lg">
                  {key}
                </label>
                <div className="flex-1 flex items-center gap-2">
                  <input
                    type={sensitive && !revealed ? 'password' : 'text'}
                    value={value}
                    onChange={(e) => handleChange(key, e.target.value)}
                    className="flex-1 border border-slate-200 rounded-lg px-3.5 py-2 text-sm font-mono bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  {sensitive && (
                    <button
                      onClick={() => toggleReveal(key)}
                      className="px-3 py-2 text-xs text-slate-500 hover:text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors font-medium w-14 text-center"
                    >
                      {revealed ? 'Hide' : 'Show'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
