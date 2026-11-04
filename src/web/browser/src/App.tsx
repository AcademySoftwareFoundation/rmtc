// SPDX-License-Identifier: Apache-2.0
// Copyright Contributors to the RMTC Project

import { useState } from 'react'
import './App.css'
import { Box, Stack, TextField, IconButton } from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import MenuItem from '@mui/material/MenuItem'

import DataTable from './components/DataTable.tsx'
import type { Resource } from './api/client.ts'
import { RESOURCES } from './api/client.ts'


function App() {
  const [name, setName] = useState('')
  const [draft, setDraft] = useState('')
  const [resource, setResource] = useState<Resource>('entities')


  const onSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setName(draft.trim())
  }

  return (
    <>
      <Stack spacing={2} sx={{ height: '98dvh', p: 2 }}>
        <Stack>
          <h1> RMTC </h1>
        </Stack>
        <Stack 
          component="form" 
          onSubmit={onSearch}
          direction="row" 
          spacing={1} 
          sx={{ alignItems: 'center' }}
        >
          <TextField 
            id="search" 
            label="Search RMTC" 
            variant="outlined" 
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            sx={{ flex: 1 }}
          />
          <TextField
            select
            label="Type"
            value={resource}
            onChange={(e) => setResource(e.target.value as Resource)}
            sx={{ minWidth: 140 }}
          >
            {RESOURCES.map((resource) => (
                <MenuItem key={resource} value={resource}> {resource[0].toUpperCase() + resource.slice(1)} </MenuItem>
            ))}
          </TextField>
          <IconButton type="submit" aria-label="search">
            <SearchIcon />
          </IconButton>
        </Stack>
        <Box sx={{ flex: 1, minHeight: 0 }}>
          <DataTable name={name} resource={resource} />
        </Box>
      </Stack>
    </>
  )
}

export default App
