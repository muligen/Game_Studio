import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { RequirementsBoard } from '@/pages/RequirementsBoard'
import { BugsBoard } from '@/pages/BugsBoard'
import { DesignEditor } from '@/pages/DesignEditor'
import './App.css'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="bg-white border-b">
          <div className="container mx-auto px-4 py-4">
            <nav className="flex gap-6">
              <Link to="/requirements" className="hover:underline">Requirements</Link>
              <Link to="/bugs" className="hover:underline">Bugs</Link>
            </nav>
          </div>
        </div>
        <Routes>
          <Route path="/" element={<RequirementsBoard />} />
          <Route path="/requirements" element={<RequirementsBoard />} />
          <Route path="/bugs" element={<BugsBoard />} />
          <Route path="/design-docs/:id" element={<DesignEditor />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
