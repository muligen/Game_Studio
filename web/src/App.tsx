import { useState } from 'react'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-8">
          Game Studio
        </h1>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-2xl font-semibold text-gray-800 mb-4">
            Welcome to Game Studio
          </h2>
          <p className="text-gray-600 mb-4">
            This is the web interface for the Game Studio project.
          </p>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-blue-800 mb-2">
              Frontend Status: <span className="font-semibold">Running</span>
            </p>
            <p className="text-blue-800 mb-2">
              Backend: <span className="font-semibold">http://localhost:8000</span>
            </p>
            <p className="text-blue-800">
              API Proxy: <span className="font-semibold">Enabled</span>
            </p>
          </div>

          <div className="mt-6">
            <button
              onClick={() => {
                setCount((count) => count + 1)
              }}
              className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded-md transition-colors"
            >
              Count is {count}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
