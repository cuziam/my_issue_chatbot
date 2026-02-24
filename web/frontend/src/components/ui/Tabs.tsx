interface Tab {
  key: string
  label: string
  hasContent?: boolean
  badge?: string | number
  dot?: boolean
}

interface TabsProps {
  tabs: Tab[]
  activeKey: string
  onChange: (key: string) => void
}

export default function Tabs({ tabs, activeKey, onChange }: TabsProps) {
  return (
    <nav className="flex gap-0.5 overflow-x-auto">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`whitespace-nowrap px-3.5 py-2.5 text-sm font-medium rounded-t-lg transition-colors relative ${
            activeKey === tab.key
              ? 'bg-slate-50 text-blue-700 border border-slate-200 border-b-white -mb-px z-10'
              : tab.hasContent !== false
                ? 'text-slate-600 hover:text-slate-800 hover:bg-slate-50'
                : 'text-slate-300'
          }`}
        >
          {tab.label}
          {tab.dot && (
            <span className="ml-1.5 inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              <span className="text-[10px] text-blue-600 font-semibold">live</span>
            </span>
          )}
          {tab.badge != null && (
            <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full bg-slate-200 text-slate-600">{tab.badge}</span>
          )}
        </button>
      ))}
    </nav>
  )
}
