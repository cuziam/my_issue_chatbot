import { useEffect, useState, useCallback } from 'react'
import { api } from '../../api/client'
import LoadingSpinner from '../../components/LoadingSpinner'
import ErrorMessage from '../../components/ErrorMessage'

export default function ConfigEditor() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null)
  const [configText, setConfigText] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)

  const loadConfig = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getConfig()
      setConfig(data)
      setConfigText(JSON.stringify(data, null, 2))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load config')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfig()
  }, [loadConfig])

  const handleTextChange = (text: string) => {
    setConfigText(text)
    setParseError(null)
    try {
      JSON.parse(text)
    } catch (e) {
      setParseError(e instanceof Error ? e.message : 'Invalid JSON')
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveMessage(null)
    try {
      const data = JSON.parse(configText)
      await api.updateConfig(data)
      setConfig(data)
      setSaveMessage({ type: 'success', text: 'Config saved successfully' })
    } catch (e) {
      setSaveMessage({ type: 'error', text: e instanceof Error ? e.message : 'Failed to save config' })
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
    return <ErrorMessage message={error} onRetry={loadConfig} />
  }

  const hasChanges = config !== null && configText !== JSON.stringify(config, null, 2)

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-800">config.json</h2>
            <p className="text-xs text-slate-400">Application configuration</p>
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
              if (config) {
                setConfigText(JSON.stringify(config, null, 2))
                setParseError(null)
              }
            }}
            disabled={!hasChanges}
            className="px-3.5 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg disabled:opacity-50 transition-colors"
          >
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !!parseError || !hasChanges}
            className="px-3.5 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 flex items-center gap-2 shadow-sm transition-colors"
          >
            {saving && <LoadingSpinner size="sm" />}
            Save
          </button>
        </div>
      </div>
      <div className="p-5">
        {parseError && (
          <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            Parse error: {parseError}
          </div>
        )}
        {saveMessage && (
          <div className={`mb-3 px-3 py-2 rounded-lg text-sm border ${
            saveMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
              : 'bg-red-50 border-red-200 text-red-700'
          }`}>
            {saveMessage.text}
          </div>
        )}
        <textarea
          value={configText}
          onChange={(e) => handleTextChange(e.target.value)}
          className="w-full h-[500px] font-mono text-sm border border-slate-200 rounded-xl p-4 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y leading-relaxed"
          spellCheck={false}
        />
      </div>
    </div>
  )
}
