// SPDX-License-Identifier: Apache-2.0
// Copyright Contributors to the RMTC Project

import { useMemo } from 'react'

import {
    DataGrid,
    type GridColDef,
} from '@mui/x-data-grid'
import Box from '@mui/material/Box'

import { useQuery } from '@tanstack/react-query'

import type { Entity, Resource } from '../api/client.ts'
import { getResource } from '../api/client.ts'


function formatValue(value: unknown): string {
    if (value === null || value === undefined) return '-'
    if (Array.isArray(value)) return value.map(formatValue).join(', ')
    if (typeof value === 'object') {
        const obj = value as Record<string, unknown>
        if ('name' in obj) return String(obj.name)  // reference: {_id, _type_name, name}
    return JSON.stringify(obj)                      // nested member object (placeholder for now)
    }
    return String(value)
}

const LEADING = ['name',]
const HIDDEN = ['_id', '_type_name', 'active', 'externals', 'instantiated_at', 'context', 'ancestors']

function columnsFor(rows: Entity[]): GridColDef[] {
    const isFilled = (value: unknown) => 
        (value !== null && value !== undefined && value !== '') 
        && !(Array.isArray(value) && value.length === 0)

    const filledProperties = new Map<string, number>()
    
    // Count which entity properties have values
    rows.forEach((row) => {
        Object.entries(row).forEach(([k, v]) => {
            const currentCount = filledProperties.get(k) ?? 0
            const increment = isFilled(v) ? 1 : 0
            filledProperties.set(k, currentCount + increment)
        })
    })
    
    // Sort properties by how many are filled
    const rest = [...filledProperties.keys()]
        .filter((k) => !LEADING.includes(k) && !HIDDEN.includes(k))
        .sort((a, b) => 
            (filledProperties.get(b)! - filledProperties.get(a)!) 
            || a.localeCompare(b),
        )
    
    // Format as a GridColDef[]
    return [...LEADING, ...rest].map((field) => ({
        field,
        headerName: field,
        minWidth: 140,
        flex: 1,
        valueGetter: (value: unknown) =>
            value !== null && typeof value === 'object' ? formatValue(value) : value,
    }))
}

export default function DataTable({ name, resource } : { name: string, resource: Resource }) {
    const queryResult = useQuery({ 
        queryKey: [resource, name], 
        queryFn: () => getResource(name, resource, undefined, false),
        enabled: !!name,
    })

    const columns = useMemo(() => columnsFor(queryResult.data ?? []), [queryResult.data])
    
    return (
        <Box sx={{ height: '100%', width: '100%' }}>
            <DataGrid 
                rows={queryResult.data ?? []}
                getRowId={(row) => row._id}
                // loading={queryResult.isLoading}
                columns={columns}
                sx={(theme) => ({
                    border: 0,
                    bgcolor: 'background.default',
                    '--DataGrid-containerBackground': theme.palette.background.default,
                    '--DataGrid-pinnedBackground': theme.palette.background.default,
                })}
            />
        </Box>
    )
}
