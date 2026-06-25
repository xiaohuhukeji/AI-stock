import request from '@/utils/request'

const screenerApi = {
  ScreenStocks: '/api/stock-screener/screen',
  AiScreen: '/api/stock-screener/ai-screen',
  GetUniverses: '/api/stock-screener/universes',
  GetSectors: '/api/stock-screener/sectors'
}

export function screenStocks (parameter) {
  return request({
    url: screenerApi.ScreenStocks,
    method: 'post',
    data: parameter
  })
}

export function aiScreenStocks (parameter) {
  return request({
    url: screenerApi.AiScreen,
    method: 'post',
    data: parameter
  })
}

export function getUniverses () {
  return request({
    url: screenerApi.GetUniverses,
    method: 'get'
  })
}

export function getSectors () {
  return request({
    url: screenerApi.GetSectors,
    method: 'get'
  })
}
