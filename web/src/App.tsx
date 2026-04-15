import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RequirementsBoard } from '@/pages/RequirementsBoard'
import './App.css'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RequirementsBoard />
    </QueryClientProvider>
  )
}

export default App
