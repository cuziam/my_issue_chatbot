import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { WebSocketProvider } from './contexts/WebSocketContext'
import { ImageLightboxProvider } from './contexts/ImageLightboxContext'
import ToastContainer from './components/ui/ToastContainer'
import ErrorBoundary from './components/ErrorBoundary'
import LoadingSpinner from './components/LoadingSpinner'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const TaskDetail = lazy(() => import('./pages/TaskDetail'))
const Jobs = lazy(() => import('./pages/Jobs'))
const Scheduler = lazy(() => import('./pages/scheduler'))
const Settings = lazy(() => import('./pages/settings'))

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/jobs', label: 'Jobs', end: false },
  { to: '/scheduler', label: 'Scheduler', end: false },
  { to: '/settings', label: 'Settings', end: false },
]

function PageLoader() {
  return (
    <div className="flex justify-center py-16">
      <LoadingSpinner size="lg" />
    </div>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-[1400px] mx-auto px-6">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-10">
              {/* Logo */}
              <NavLink to="/" className="flex items-center gap-2.5 group">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-lg flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow">
                  <span className="text-white font-bold text-sm">IM</span>
                </div>
                <span className="font-semibold text-slate-800 text-[0.95rem]">
                  InterMax <span className="text-slate-400 font-normal">Issue Bot</span>
                </span>
              </NavLink>

              {/* Nav Links */}
              <div className="flex items-center gap-1">
                {NAV_ITEMS.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `px-3.5 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? 'bg-blue-50 text-blue-700'
                          : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-[1400px] mx-auto py-6 px-6">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <WebSocketProvider>
        <ImageLightboxProvider>
          <Layout>
            <ErrorBoundary>
              <Suspense fallback={<PageLoader />}>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/tasks/:id" element={<TaskDetail />} />
                  <Route path="/jobs" element={<Jobs />} />
                  <Route path="/scheduler" element={<Scheduler />} />
                  <Route path="/settings" element={<Settings />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </Layout>
          <ToastContainer />
        </ImageLightboxProvider>
      </WebSocketProvider>
    </BrowserRouter>
  )
}
