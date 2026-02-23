import { useEffect, useState, useCallback } from 'react'
import { api } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorMessage from '../components/ErrorMessage'

type SettingsTab = 'config' | 'env' | 'inventory'

const TABS: { key: SettingsTab; label: string; icon: React.ReactNode }[] = [
  {
    key: 'config',
    label: 'Config',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    key: 'env',
    label: 'Environment',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
      </svg>
    ),
  },
  {
    key: 'inventory',
    label: 'Packages',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
    ),
  },
]

const SENSITIVE_KEYS = ['api_key', 'token', 'secret', 'password', 'key']

function isSensitiveKey(key: string): boolean {
  const lower = key.toLowerCase()
  return SENSITIVE_KEYS.some((s) => lower.includes(s))
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('config')

  return (
    <div>
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-800">Settings</h1>
        <p className="text-sm text-slate-500 mt-0.5">Manage configuration, environment, and packages</p>
      </div>

      {/* Tab Bar */}
      <div className="flex gap-1 mb-6 bg-slate-100 p-1 rounded-xl w-fit">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.key
                ? 'bg-white text-slate-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'config' && <ConfigEditor />}
      {activeTab === 'env' && <EnvEditor />}
      {activeTab === 'inventory' && <InventoryViewer />}
    </div>
  )
}

function ConfigEditor() {
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

function EnvEditor() {
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

function InventoryViewer() {
  const [packages, setPackages] = useState<Record<string, unknown>[] | null>(null)
  const [generatedAt, setGeneratedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadInventory = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getInventory()
      setPackages(data.packages)
      setGeneratedAt(data.generated_at)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load inventory')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadInventory()
  }, [loadInventory])

  const handleRefresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      const data = await api.refreshInventory()
      setPackages(data.packages)
      setGeneratedAt(new Date().toISOString())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to refresh inventory')
    } finally {
      setRefreshing(false)
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
    return <ErrorMessage message={error} onRetry={loadInventory} />
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Package Inventory</h2>
            {generatedAt && (
              <p className="text-xs text-slate-400">
                Generated {new Date(generatedAt).toLocaleString()}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 shadow-sm transition-colors"
        >
          {refreshing ? (
            <LoadingSpinner size="sm" />
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          )}
          Refresh
        </button>
      </div>
      {!packages || packages.length === 0 ? (
        <div className="px-5 py-12 text-center">
          <svg className="w-10 h-10 text-slate-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          <p className="text-sm text-slate-500">No packages found</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Package</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Version</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Components</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase">Path</th>
              </tr>
            </thead>
            <tbody>
              {packages.map((pkg, idx) => {
                const name = (pkg.name as string) || (pkg.package_name as string) || `Package ${idx + 1}`
                const version = (pkg.version as string) || '-'
                const components = Array.isArray(pkg.components)
                  ? (pkg.components as string[]).join(', ')
                  : typeof pkg.components === 'object' && pkg.components
                    ? Object.keys(pkg.components).join(', ')
                    : '-'
                const path = (pkg.path as string) || (pkg.dir as string) || '-'
                return (
                  <tr
                    key={idx}
                    className={`hover:bg-slate-50 transition-colors ${
                      idx !== packages.length - 1 ? 'border-b border-slate-100' : ''
                    }`}
                  >
                    <td className="px-4 py-2.5 text-sm font-semibold text-slate-800">{name}</td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs font-mono text-slate-600 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
                        {version}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-sm text-slate-600">{components}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-500 font-mono truncate max-w-xs" title={path}>
                      {path}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
