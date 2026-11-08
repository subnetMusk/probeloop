import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '@/api/rest'
import type { AddFactIn, FactView, PreparationView } from '@/api/rest'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

const ORIGINS: Record<string, string> = {
  declared: 'Declared',
  inferred: 'Inferred',
  user: 'Added',
}

function FactRow({
  fact,
  act,
}: {
  fact: FactView
  act: (
    id: string,
    review: 'confirmed' | 'excluded' | 'corrected' | 'pending',
    corrected?: string,
  ) => void
}) {
  const [draft, setDraft] = useState<string | null>(null)
  return (
    <li className="flex flex-col gap-3 border-b py-4 last:border-0" data-testid="context-fact">
      <div className="flex flex-wrap gap-2">
        <Badge variant={fact.origin === 'inferred' ? 'secondary' : 'outline'}>
          {ORIGINS[fact.origin]}
        </Badge>
        <Badge variant="outline">{fact.kind.replaceAll('_', ' ')}</Badge>
        {fact.review === 'corrected' && <Badge variant="secondary">Corrected by you</Badge>}
        <span className="text-xs text-muted-foreground">{fact.review}</span>
      </div>
      <p className={fact.review === 'excluded' ? 'text-muted-foreground line-through' : ''}>
        {fact.text}
      </p>
      {fact.quote && (
        <blockquote className="border-l-2 pl-3 text-sm text-muted-foreground">
          “{fact.quote}”{' '}
          <span className="block text-xs">
            {fact.review === 'corrected' ? 'Original source quote' : 'Verified source quote'}
          </span>
        </blockquote>
      )}
      {fact.origin === 'inferred' && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          No verified quote. Check this interpretation before keeping it.
        </p>
      )}
      {draft !== null ? (
        <div className="flex flex-col gap-2">
          <Textarea
            aria-label="Corrected fact"
            maxLength={400}
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value)
            }}
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={!draft.trim()}
              onClick={() => {
                act(fact.id, 'corrected', draft)
                setDraft(null)
              }}
            >
              Save correction
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setDraft(null)
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              act(fact.id, 'confirmed')
            }}
          >
            Confirm
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setDraft(fact.text)
            }}
          >
            Correct
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              act(fact.id, fact.review === 'excluded' ? 'pending' : 'excluded')
            }}
          >
            {fact.review === 'excluded' ? 'Include again' : 'Exclude'}
          </Button>
        </div>
      )}
    </li>
  )
}

function Area({
  preparation,
  save,
}: {
  preparation: PreparationView
  save: (area: string, seniority: string) => void
}) {
  const [area, setArea] = useState(preparation.area?.area ?? '')
  const [seniority, setSeniority] = useState(preparation.area?.seniority ?? '')
  return (
    <Card>
      <CardHeader>
        <CardTitle>Confirm your professional area</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          Without a job offer, this is a getting-to-know interview for a generic company in your
          area. Requirement matching does not apply.
        </p>
        <p className="text-sm">{preparation.area?.rationale}</p>
        <Label htmlFor="area">Professional area</Label>
        <Input
          id="area"
          maxLength={120}
          value={area}
          onChange={(event) => {
            setArea(event.target.value)
          }}
        />
        <Label htmlFor="seniority">Seniority</Label>
        <Input
          id="seniority"
          maxLength={40}
          value={seniority}
          onChange={(event) => {
            setSeniority(event.target.value)
          }}
        />
        <Button
          className="self-start"
          disabled={!area.trim()}
          onClick={() => {
            save(area, seniority)
          }}
        >
          {preparation.area?.confirmed ? 'Save area' : 'Confirm area'}
        </Button>
        {preparation.area?.confirmed && <p className="text-sm text-emerald-700">Area confirmed</p>}
      </CardContent>
    </Card>
  )
}

function AddFact({ save }: { save: (body: AddFactIn) => void }) {
  const [subject, setSubject] = useState<AddFactIn['subject']>('candidate')
  const [statement, setStatement] = useState('')
  return (
    <div className="flex flex-col gap-3">
      <h3 className="font-medium">Add a fact</h3>
      <div className="flex gap-2">
        <Button
          variant={subject === 'candidate' ? 'default' : 'outline'}
          onClick={() => {
            setSubject('candidate')
          }}
        >
          Candidate
        </Button>
        <Button
          variant={subject === 'job' ? 'default' : 'outline'}
          onClick={() => {
            setSubject('job')
          }}
        >
          Job
        </Button>
      </div>
      <Textarea
        aria-label="New fact"
        maxLength={400}
        value={statement}
        onChange={(event) => {
          setStatement(event.target.value)
        }}
      />
      <Button
        className="self-start"
        disabled={!statement.trim()}
        onClick={() => {
          save({ subject, kind: subject === 'candidate' ? 'other' : 'requirement', statement })
          setStatement('')
        }}
      >
        Add fact
      </Button>
    </div>
  )
}

export function ContextReview({
  preparation,
  onApproved,
}: {
  preparation: PreparationView
  onApproved: (id: string) => void
}) {
  const queryClient = useQueryClient()
  const update = useMutation({
    mutationFn: (task: () => Promise<PreparationView>) => task(),
    onSuccess: (view) => {
      queryClient.setQueryData(['preparation', view.id], view)
    },
  })
  const approve = useMutation({
    mutationFn: () => api.approve(preparation.id),
    onSuccess: (snapshot) => {
      onApproved(snapshot.id)
    },
  })
  const error = update.error ?? approve.error
  const byId = new Map(preparation.facts.map((f) => [f.id, f]))
  const ready = preparation.job_mode !== 'none' || preparation.area?.confirmed === true
  return (
    <div className="flex flex-col gap-6" data-testid="context-review">
      <h2 className="text-2xl font-semibold">Review the interview context</h2>
      <p className="text-muted-foreground">
        Check the extracted facts. Correct or exclude mistakes before approving. Declared means the
        quote was found in the document; it does not independently verify the claim.
      </p>
      {preparation.job_mode === 'generated' && (
        <Badge variant="secondary">Job offer drafted from your description</Badge>
      )}
      {preparation.documents.map(
        (document) =>
          document.warnings.length > 0 && (
            <div key={document.id} role="alert" className="rounded-lg border border-amber-500 p-4">
              <h3 className="font-medium">{document.title}</h3>
              {document.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          ),
      )}
      <fieldset
        disabled={update.isPending || approve.isPending}
        className="flex min-w-0 flex-col gap-6"
      >
        {preparation.job_mode === 'none' && (
          <Area
            preparation={preparation}
            save={(area, seniority) => {
              update.mutate(() => api.setArea(preparation.id, { area, seniority }))
            }}
          />
        )}
        {(['candidate', 'job'] as const).map((subject) => (
          <Card key={subject}>
            <CardHeader>
              <CardTitle>{subject === 'candidate' ? 'Candidate facts' : 'Job facts'}</CardTitle>
            </CardHeader>
            <CardContent>
              <ul>
                {preparation.facts
                  .filter((f) => f.subject === subject)
                  .map((fact) => (
                    <FactRow
                      key={fact.id}
                      fact={fact}
                      act={(id, review, corrected) => {
                        update.mutate(() =>
                          api.reviewFact(preparation.id, id, { review, corrected }),
                        )
                      }}
                    />
                  ))}
              </ul>
              {!preparation.facts.some((f) => f.subject === subject) && (
                <p className="text-muted-foreground">No facts extracted.</p>
              )}
            </CardContent>
          </Card>
        ))}
        {preparation.job_mode !== 'none' && (
          <Card>
            <CardHeader>
              <CardTitle role="heading" aria-level={3}>
                Requirement matrix
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr>
                    <th className="p-2">Requirement</th>
                    <th className="p-2">Status</th>
                    <th className="p-2">Supporting facts</th>
                  </tr>
                </thead>
                <tbody>
                  {preparation.matches.map((match) => (
                    <tr key={match.requirement_id} className="border-t">
                      <td className="p-2">{byId.get(match.requirement_id)?.text}</td>
                      <td className="p-2">{match.status.replaceAll('_', ' ')}</td>
                      <td className="p-2">
                        {match.fact_ids.map((id) => byId.get(id)?.text).join('; ') ||
                          'No evidence shown'}
                        <p className="text-xs text-muted-foreground">
                          Model interpretation: {match.rationale}
                        </p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}
        <AddFact
          save={(body) => {
            update.mutate(() => api.addFact(preparation.id, body))
          }}
        />
        {error && (
          <p role="alert" className="text-destructive">
            {error.message}
          </p>
        )}
        <Button
          disabled={!ready}
          onClick={() => {
            approve.mutate()
          }}
        >
          {approve.isPending ? 'Approving…' : 'Approve context and continue'}
        </Button>
        {!ready && (
          <p className="text-sm text-muted-foreground">
            Confirm your professional area before continuing.
          </p>
        )}
      </fieldset>
    </div>
  )
}
