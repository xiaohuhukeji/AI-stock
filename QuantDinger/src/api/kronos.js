import request from '@/utils/request'

export const KRONOS_TIMEOUT = 300000

export function kronosPredict (params) {
  return request({
    url: '/api/kronos/predict',
    method: 'get',
    params,
    timeout: KRONOS_TIMEOUT
  })
}

export function kronosHealth () {
  return request({
    url: '/api/kronos/health',
    method: 'get'
  })
}

export function kronosModels () {
  return request({
    url: '/api/kronos/models',
    method: 'get'
  })
}

export function kronosLoadModel (model) {
  return request({
    url: '/api/kronos/load-model',
    method: 'post',
    data: { model },
    timeout: KRONOS_TIMEOUT
  })
}
