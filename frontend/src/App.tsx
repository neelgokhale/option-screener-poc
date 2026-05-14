import { Routes, Route } from 'react-router-dom'
import AppHeader from './components/AppHeader'
import ScreenerPage from './pages/ScreenerPage'
import ReportPage from './pages/ReportPage'

function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <AppHeader />
      <Routes>
        <Route path="/" element={<ScreenerPage />} />
        <Route path="/report" element={<ReportPage />} />
      </Routes>
    </div>
  )
}

export default App
