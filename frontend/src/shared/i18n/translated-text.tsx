import { translate } from './legacy'
import { useLanguage } from '@/shared/lib/preferences'

export function T({ text }: { text: string }) {
  return translate(text, useLanguage())
}
