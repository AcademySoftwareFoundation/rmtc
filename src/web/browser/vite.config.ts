// SPDX-License-Identifier: Apache-2.0
// Copyright Contributors to the RMTC Project

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Proxy for API routes so that web app and server keep same origin
  server: {
    proxy: {
      '^/v[0-9]+(?:/|\\?|$)': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      }
    }
  }
})
