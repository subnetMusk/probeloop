import { useLanguage } from '@/shared/lib/preferences'
import type { Language } from '@/shared/lib/preferences'

/**
 * Typed dictionaries (ADR 0014). Each slice defines its messages once per language with
 * `defineMessages`; English is the reference shape, so a key missing in Italian is a type error.
 * Values are text, lists of text, or functions of typed parameters for counts and names.
 */
export type MessageValue = string | readonly string[] | ((...args: never[]) => string)
export interface MessageTree {
  readonly [key: string]: MessageValue | MessageTree
}

/** The same keys and parameters as `T`, with any text. */
export type Translation<T> = {
  readonly [K in keyof T]: T[K] extends string
    ? string
    : T[K] extends readonly string[]
      ? readonly string[]
      : T[K] extends (...args: infer A) => string
        ? (...args: A) => string
        : Translation<T[K]>
}

export type Dictionary<T extends MessageTree> = Readonly<Record<Language, Translation<T>>>

export function defineMessages<const T extends MessageTree>(messages: {
  en: T
  it: Translation<T>
}): Dictionary<T> {
  // English literals are narrower than `Translation<T>`, which widens them to text.
  return { en: messages.en as unknown as Translation<T>, it: messages.it }
}

/** The messages of `dictionary` in `language`, for code outside React (view models, tests). */
export function getMessages<T extends MessageTree>(
  dictionary: Dictionary<T>,
  language: Language,
): Translation<T> {
  return dictionary[language]
}

/** The messages of `dictionary` in the interface language; re-renders when it changes. */
export function useMessages<T extends MessageTree>(dictionary: Dictionary<T>): Translation<T> {
  return dictionary[useLanguage()]
}

/** Picks the form of a count by the language's plural rules (`one` or `other`). */
export function plural(
  count: number,
  language: Language,
  forms: { one: string; other: string },
): string {
  const rule = new Intl.PluralRules(language === 'it' ? 'it-IT' : 'en-GB').select(count)
  return rule === 'one' ? forms.one : forms.other
}

/** Keys of a message tree as dotted paths, to compare languages in tests. */
export function messageKeys(tree: MessageTree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([key, value]) =>
    typeof value === 'object' && !Array.isArray(value)
      ? messageKeys(value as MessageTree, `${prefix}${key}.`)
      : [`${prefix}${key}`],
  )
}
