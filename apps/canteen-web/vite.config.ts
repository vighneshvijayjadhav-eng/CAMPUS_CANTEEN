import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

declare const process: { env: Record<string, string | undefined> }

// Local development proxies /api to the API; override with VITE_API_PROXY=http://host:port.
const target = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000'

export default defineConfig({ plugins: [react()], server: { proxy: { '/api': target } } })
