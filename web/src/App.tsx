import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { RequirementsBoard } from '@/pages/RequirementsBoard'
import './App.css'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<RequirementsBoard />} />
          <Route path="/requirements" element={<RequirementsBoard />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
