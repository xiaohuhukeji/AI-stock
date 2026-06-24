import Vue from 'vue'
import VueI18n from 'vue-i18n'
import storage from 'store'
import moment from 'moment'
import enUS from './lang/en-US'
import zhCN from './lang/zh-CN'

Vue.use(VueI18n)

export const defaultLang = 'zh-CN'

const messages = {
  'en-US': {
    ...enUS
  },
  [defaultLang]: {
    ...zhCN
  }
}

const localeLoaders = {
  'ar-SA': () => import('./lang/ar-SA.js'),
  'de-DE': () => import('./lang/de-DE.js'),
  'fr-FR': () => import('./lang/fr-FR.js'),
  'ja-JP': () => import('./lang/ja-JP.js'),
  'ko-KR': () => import('./lang/ko-KR.js'),
  'th-TH': () => import('./lang/th-TH.js'),
  'vi-VN': () => import('./lang/vi-VN.js'),
  'zh-CN': () => import('./lang/zh-CN.js'),
  'zh-TW': () => import('./lang/zh-TW.js')
}

const i18n = new VueI18n({
  silentTranslationWarn: true,
  locale: defaultLang,
  fallbackLocale: defaultLang,
  messages
})

const loadedLanguages = [defaultLang]

function setI18nLanguage (lang) {
  i18n.locale = lang
  const html = document.documentElement
  const isRtl = /^ar/i.test(lang)
  if (html) {
    html.setAttribute('lang', lang)
    html.setAttribute('dir', isRtl ? 'rtl' : 'ltr')
  }
  if (document.body) {
    document.body.setAttribute('dir', isRtl ? 'rtl' : 'ltr')
    document.body.classList.toggle('rtl', isRtl)
  }
  return lang
}

export async function loadLanguageAsync (lang = defaultLang) {
  storage.set('lang', lang)
  if (i18n.locale === lang) return lang

  if (!loadedLanguages.includes(lang)) {
    const loadLocale = localeLoaders[lang]
    if (!loadLocale) return setI18nLanguage(defaultLang)

    const msg = await loadLocale()
    const locale = msg.default
    i18n.setLocaleMessage(lang, locale)
    loadedLanguages.push(lang)
    moment.updateLocale(locale.momentName, locale.momentLocale)
  }

  return setI18nLanguage(lang)
}

export function i18nRender (key) {
  return i18n.t(`${key}`)
}

export default i18n
