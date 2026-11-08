import { Label } from '@/shared/ui/label'
import { Card, CardHeader, CardTitle, CardContent } from '@/shared/ui/card'
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/shared/ui/select'
import { setLanguage, setTheme, setVolume, usePreferences } from '@/shared/lib/preferences'
import { DataControls } from '@/features/data-controls'
import { ExecutionProfileSettings } from '@/features/execution-profile'

export function SettingsPage() {
  const preferences = usePreferences()
  const it = preferences.language === 'it'
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
      <h1 className="text-3xl font-semibold">{it ? 'Impostazioni' : 'Settings'}</h1>
      <Card>
        <CardHeader>
          <CardTitle>{it ? 'Preferenze dell’app' : 'Application preferences'}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <Label htmlFor="app-language">{it ? 'Lingua' : 'Language'}</Label>
            <Select
              value={preferences.language}
              onValueChange={(value) => {
                setLanguage(value === 'en' ? 'en' : 'it')
              }}
            >
              <SelectTrigger id="app-language">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="it">Italiano</SelectItem>
                <SelectItem value="en">English</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              {it
                ? 'Lingua dell’interfaccia e predefinita per nuovi colloqui e report. Ogni colloquio può usare una lingua diversa.'
                : 'Interface language and default for new interviews and reports. Each interview can override it.'}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="app-volume">
              {it ? 'Volume dell’intervistatore' : 'Interviewer volume'} ·{' '}
              {Math.round(preferences.volume * 100)}%
            </Label>
            <input
              id="app-volume"
              type="range"
              min="0"
              max="100"
              step="1"
              value={Math.round(preferences.volume * 100)}
              onChange={(event) => {
                setVolume(Number(event.target.value) / 100)
              }}
              className="w-full accent-indigo-600"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="app-theme">{it ? 'Tema' : 'Theme'}</Label>
            <Select
              value={preferences.theme}
              onValueChange={(value) => {
                setTheme(value === 'light' || value === 'dark' ? value : 'system')
              }}
            >
              <SelectTrigger id="app-theme">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="light">{it ? 'Chiaro' : 'Light'}</SelectItem>
                <SelectItem value="dark">{it ? 'Scuro' : 'Dark'}</SelectItem>
                <SelectItem value="system">{it ? 'Come il sistema' : 'System'}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
      <ExecutionProfileSettings />
      <DataControls />
    </main>
  )
}
