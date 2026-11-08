import { PreferencesEffects } from '@/app/preferences/preferences-effects'
import { Layout } from '@/widgets/app-shell'

/** The root route: global effects of the preferences, then the app shell. */
export function Root() {
  return (
    <>
      <PreferencesEffects />
      <Layout />
    </>
  )
}
