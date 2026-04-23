import { useState } from 'react'

const DEFAULT_WORKSPACE = '.'

export function useWorkspace() {
  const [workspace, setWorkspace] = useState(DEFAULT_WORKSPACE)

  return { workspace, setWorkspace }
}
