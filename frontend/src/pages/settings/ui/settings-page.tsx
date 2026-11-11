import { Label } from '@/shared/ui/label'
import { Page, PageHeader } from '@/shared/ui/page-header'
import { Card, CardHeader, CardTitle, CardContent } from '@/shared/ui/card'
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/shared/ui/select'
import { setLanguage, setTheme, setVolume, usePreferences } from '@/shared/lib/preferences'
import { DataControls } from '@/features/data-controls'
import { ExecutionProfileSettings } from '@/features/execution-profile'
import { InstallationSettings, useInstallation } from '@/features/installation'
import { TocLayout } from '@/shared/ui/page-toc'
import { Link } from '@tanstack/react-router'

export function SettingsPage() {
  const preferences = usePreferences()
  const it = preferences.language === 'it'
  const managed = useInstallation().data?.managed === true
  const sections = [
    { id: 'tools', label: it ? 'Strumenti di elaborazione' : 'Processing tools' },
    ...(managed
      ? [{ id: 'installation', label: it ? 'Installazione e modelli' : 'Installation and models' }]
      : []),
    { id: 'preferences', label: it ? 'Preferenze dell’app' : 'Application preferences' },
    { id: 'data', label: it ? 'I tuoi dati' : 'Your data' },
  ]
  return (
    <Page>
      <PageHeader
        title={it ? 'Impostazioni' : 'Settings'}
        description={
          it
            ? 'Dove girano i modelli, quali componenti sono installati e come gestire i tuoi dati. Non sai da dove partire? Usa la configurazione guidata.'
            : 'Where the models run, which components are installed and how to manage your data. Not sure where to start? Use the guided setup.'
        }
      />
      <TocLayout label={it ? 'In questa pagina' : 'On this page'} items={sections}>
        <section
          id="tools"
          aria-label={sections[0]?.label}
          className="flex scroll-mt-6 flex-col gap-4"
        >
          <ExecutionProfileSettings />
          <Link
            to="/setup"
            className="self-start text-sm text-brand-text underline underline-offset-4"
          >
            {it ? 'Apri la configurazione guidata' : 'Open guided setup'}
          </Link>
        </section>
        {managed && (
          <section id="installation" className="scroll-mt-6">
            <InstallationSettings />
          </section>
        )}
        <section id="preferences" className="scroll-mt-6">
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
                  className="w-full accent-brand"
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
        </section>
        <section id="data" className="scroll-mt-6">
          <DataControls />
        </section>
      </TocLayout>
    </Page>
  )
}
