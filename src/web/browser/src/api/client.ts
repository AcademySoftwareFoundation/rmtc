// SPDX-License-Identifier: Apache-2.0
// Copyright Contributors to the RMTC Project

import axios from 'axios'
export const api = axios.create({ baseURL: '/v1'})

export type Entity = {
    _id: string; 
    _type_name: string; 
    name: string; 
    [k: string]: unknown 
}

export const RESOURCES = [
    'entities', 'models', 'runs', 'licenses', 'solutions', 'datasets', 'inferences', 'assets',
] as const

export type Resource = (typeof RESOURCES)[number]

export const getResource = (name: string, resource: Resource, limit?: number, exact?: boolean) =>
    api.get<{ results: Entity[] }>(`${resource}`, { params: { name, limit, exact } })
        .then(r => r.data.results)
