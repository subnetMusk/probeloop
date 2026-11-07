import './index.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { AudioProvider } from '@/audio/audio-provider'
import { router } from '@/router'

const queryClient = new QueryClient()
const root = document.getElementById('root')
if (!root) throw new Error('missing #root element')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AudioProvider>
        <RouterProvider router={router} />
      </AudioProvider>
    </QueryClientProvider>
  </StrictMode>,
)
