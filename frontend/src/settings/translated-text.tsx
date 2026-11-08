import { translate } from './i18n'
import { useLanguage } from './preferences'

export function T({ text }: { text: string }) {
  return translate(text, useLanguage())
}
