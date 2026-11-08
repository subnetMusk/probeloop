import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ChevronRightIcon, PlusIcon, Trash2Icon } from 'lucide-react'

import { api } from '@/api/rest'
import type { SessionSummary } from '@/api/rest'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { INTERVIEW_TYPES, STATUS_LABELS, dateTime } from '@/lib/format'
import { ProgressHistory } from '@/reports/progress-history'
import { T } from '@/settings/translated-text'
import { localise } from '@/settings/i18n'

function StatusBadge({ status }: { status: string }) {
  const variant = status === 'failed' ? 'destructive' : status === 'ended' ? 'secondary' : 'outline'
  return (
    <Badge variant={variant}>
      <T text={STATUS_LABELS[status] ?? status} />
    </Badge>
  )
}

function Row({ session, onDelete }: { session: SessionSummary; onDelete: () => void }) {
  return (
    <li className="flex items-center gap-4 px-4 py-3" data-testid="session-row">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">
            <T text={INTERVIEW_TYPES[session.interview_type] ?? session.interview_type} />
            <T text={' interview'} />
          </span>
          <StatusBadge status={session.status} />
        </div>
        <span className="text-sm text-muted-foreground">
          {dateTime(session.created_at)} · {session.language.toUpperCase()}
        </span>
      </div>
      <Button
        variant="ghost"
        size="icon"
        aria-label={localise('Delete the interview')}
        onClick={onDelete}
      >
        <Trash2Icon />
      </Button>
      <Button asChild variant="outline">
        <Link to="/sessions/$sessionId" params={{ sessionId: session.id }}>
          <T text={'Open'} />
          <ChevronRightIcon data-icon="inline-end" />
        </Link>
      </Button>
    </li>
  )
}

/** Past interviews, newest first. */
export function SessionsPage() {
  const queryClient = useQueryClient()
  const sessions = useQuery({ queryKey: ['sessions'], queryFn: api.sessions })
  const remove = useMutation({
    mutationFn: api.deleteSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  })

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10">
      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-3xl font-semibold tracking-tight">
            <T text={'Your interviews'} />
          </h1>
          <p className="text-muted-foreground">
            <T text={'Transcripts, recordings and reports of the interviews you practised.'} />
          </p>
        </div>
        <Button asChild>
          <Link to="/">
            <PlusIcon data-icon="inline-start" />
            <T text={'New interview'} />
          </Link>
        </Button>
      </div>
      {sessions.error && (
        <Alert variant="destructive">
          <AlertTitle>
            <T text={'The interviews could not be loaded'} />
          </AlertTitle>
          <AlertDescription>{sessions.error.message}</AlertDescription>
        </Alert>
      )}
      {remove.error && (
        <Alert variant="destructive">
          <AlertTitle>
            <T text={'The interview could not be deleted'} />
          </AlertTitle>
          <AlertDescription>{remove.error.message}</AlertDescription>
        </Alert>
      )}
      <Card className="py-0">
        <CardContent className="px-0">
          {sessions.data?.length === 0 && (
            <p className="px-4 py-10 text-center text-muted-foreground">
              <T text={'No interviews yet. Start one to see it here.'} />
            </p>
          )}
          <ul className="divide-y">
            {sessions.data?.map((session) => (
              <Row
                key={session.id}
                session={session}
                onDelete={() => {
                  const sure = window.confirm(
                    'Delete this interview with its transcript, recordings and reports? This cannot be undone.',
                  )
                  if (sure) remove.mutate(session.id)
                }}
              />
            ))}
          </ul>
        </CardContent>
      </Card>
      <ProgressHistory />
    </div>
  )
}
