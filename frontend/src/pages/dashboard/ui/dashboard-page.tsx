import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import {
  ClockIcon,
  FileCheckIcon,
  MessagesSquareIcon,
  PlusIcon,
  TrendingUpIcon,
} from 'lucide-react'

import { cvCheckHistoryQuery } from '@/entities/cv-check'
import { interviewHistoryQuery, interviewLabels, labelOf } from '@/entities/interview'
import { defineMessages, useMessages } from '@/shared/i18n'
import { minutes, score } from '@/shared/lib/format'
import { useLanguage } from '@/shared/lib/preferences'
import { Button } from '@/shared/ui/button'
import { StatTile } from '@/shared/ui/stat-tile'
import { CvCheckList } from '@/widgets/cv-check-list'
import { InterviewHistory } from '@/widgets/interview-history'
import { ProfileList } from '@/widgets/profile-list'
import { CvTrend, InterviewTrend } from '@/widgets/progress-trends'
import { kpisOf } from '../model/kpis'

const messages = defineMessages({
  en: {
    title: 'Dashboard',
    subtitle: 'Your practice at a glance.',
    start: 'New interview',
    summary: 'Summary',
    interviews: 'Interviews',
    thisMonth: (count: number) => `${String(count)} this month`,
    latest: 'Latest score',
    latestType: (type: string) => `${type} interview`,
    delta: 'compared with the previous interview of the same type',
    none: '—',
    practice: 'Practice time',
    practiceNote: 'Interview time without pauses',
    cvChecks: 'CV checks',
    latestCv: (value: string) => `Latest: ${value} / 5`,
    welcome: {
      title: 'Practise your first interview',
      text: 'Choose the interview, add your CV and the job offer, check what the analysis understood, then answer out loud. Reports and trends appear here.',
    },
  },
  it: {
    title: 'Dashboard',
    subtitle: 'I tuoi allenamenti in sintesi.',
    start: 'Nuovo colloquio',
    summary: 'Riepilogo',
    interviews: 'Colloqui',
    thisMonth: (count: number) => `${String(count)} questo mese`,
    latest: 'Ultimo punteggio',
    latestType: (type: string) => `Colloquio ${type.toLowerCase()}`,
    delta: 'rispetto al colloquio precedente dello stesso tipo',
    none: '—',
    practice: 'Tempo di allenamento',
    practiceNote: 'Durata dei colloqui senza pause',
    cvChecks: 'CV check',
    latestCv: (value: string) => `Ultimo: ${value} / 5`,
    welcome: {
      title: 'Fai il tuo primo colloquio',
      text: 'Scegli il colloquio, aggiungi CV e offerta, controlla ciò che l’analisi ha capito, poi rispondi a voce. Qui compariranno report e andamenti.',
    },
  },
})

/** The landing page: headline numbers, the two trends, and short pages of history. */
export function DashboardPage() {
  const t = useMessages(messages)
  const labels = useMessages(interviewLabels)
  const language = useLanguage()
  const interviews = useQuery(interviewHistoryQuery)
  const checks = useQuery(cvCheckHistoryQuery)
  const [now] = useState(() => Date.now() / 1000)
  const kpis = kpisOf(interviews.data ?? [], checks.data ?? [], now)
  const fresh = interviews.data?.length === 0 && checks.data?.length === 0
  const delta = kpis.latest?.delta
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-6 py-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-semibold tracking-tight">{t.title}</h1>
          <p className="text-muted-foreground">{t.subtitle}</p>
        </div>
        <Button
          asChild
          size="lg"
          className="h-10 bg-brand px-4 text-brand-foreground hover:bg-brand/90"
        >
          <Link to="/new-interview">
            <PlusIcon data-icon="inline-start" />
            {t.start}
          </Link>
        </Button>
      </header>

      {fresh ? (
        <section className="relative overflow-hidden rounded-2xl p-8 ring-1 ring-foreground/10">
          {/* The accent stays decorative: text sits on the plain surface for its contrast. */}
          <div
            aria-hidden="true"
            className="absolute inset-x-0 top-0 h-1.5"
            style={{ background: 'var(--brand-gradient)' }}
          />
          <h2 className="text-2xl font-semibold">{t.welcome.title}</h2>
          <p className="mt-2 max-w-xl text-muted-foreground">{t.welcome.text}</p>
          <Button asChild className="mt-6 bg-brand text-brand-foreground hover:bg-brand/90">
            <Link to="/new-interview">{t.start}</Link>
          </Button>
        </section>
      ) : (
        <>
          <section aria-label={t.summary} className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatTile
              label={t.interviews}
              value={kpis.interviews}
              note={t.thisMonth(kpis.thisMonth)}
              icon={<MessagesSquareIcon className="size-4" />}
            />
            <StatTile
              label={t.latest}
              value={kpis.latest ? score(kpis.latest.overall, language) : t.none}
              unit={kpis.latest ? '/ 5' : undefined}
              delta={
                delta === null || delta === undefined
                  ? undefined
                  : {
                      text: `${delta > 0 ? '+' : ''}${score(delta, language)}`,
                      direction: delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat',
                    }
              }
              deltaLabel={t.delta}
              note={kpis.latest && t.latestType(labelOf(labels, 'types', kpis.latest.type))}
              icon={<TrendingUpIcon className="size-4" />}
            />
            <StatTile
              label={t.practice}
              value={minutes(kpis.practiceSeconds)}
              note={t.practiceNote}
              icon={<ClockIcon className="size-4" />}
            />
            <StatTile
              label={t.cvChecks}
              value={kpis.cvChecks}
              note={kpis.latestCv !== null && t.latestCv(score(kpis.latestCv, language))}
              icon={<FileCheckIcon className="size-4" />}
            />
          </section>
          <div className="grid gap-6 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <InterviewTrend />
            </div>
            <div className="lg:col-span-2">
              <CvTrend />
            </div>
          </div>
        </>
      )}
      <div className="grid items-start gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <InterviewHistory pageSize={5} />
        </div>
        <div className="flex flex-col gap-6 lg:col-span-2">
          <CvCheckList pageSize={3} />
          <ProfileList pageSize={4} />
        </div>
      </div>
    </main>
  )
}
