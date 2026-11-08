import { useMutation, useQuery } from '@tanstack/react-query'
import { Loader2Icon, PlusIcon, Trash2Icon } from 'lucide-react'
import { useState } from 'react'

import { api } from '@/api/rest'
import type { DocumentView, PrepareIn, ProfileView, ResourceIn } from '@/api/rest'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { InterviewSetup } from '@/pages/interview-setup'

import { ContextReview } from './context-review'
import {
  emptyResource,
  hasContent,
  isComplete,
  isEmpty,
  resourcesChanged,
  withEmptyRow,
} from './resources'
import type { ResourceRow } from './resources'
import { PREPARATION_KEY } from './setup-state'
import { setLanguage as saveLanguage, useLanguage } from '@/settings/preferences'
import { T } from '@/settings/translated-text'
import { localise } from '@/settings/i18n'

const ACCEPT = '.txt,.md,.json,.xml,.html,.docx,.pdf'
type Language = 'it' | 'en'
type OfferMode = 'none' | 'text' | 'file' | 'describe'
interface DocumentInput {
  text: string
  file: File | null
  document: DocumentView | null
}
const emptyInput = (): DocumentInput => ({ text: '', file: null, document: null })

async function saveDocument(
  kind: 'cv' | 'job_offer',
  title: string,
  input: DocumentInput,
  generated = false,
): Promise<DocumentView | null> {
  if (input.document) return input.document
  if (input.file) return api.uploadDocument(kind, title, input.file)
  if (input.text.trim()) return api.typedDocument({ kind, title, text: input.text, generated })
  return null
}

function DocumentEditor({
  id,
  label,
  value,
  onChange,
  fileOnly = false,
  textOnly = false,
}: {
  id: string
  label: string
  value: DocumentInput
  onChange: (input: DocumentInput) => void
  fileOnly?: boolean
  textOnly?: boolean
}) {
  return (
    <div className="flex flex-col gap-3">
      {!fileOnly && (
        <>
          <Label htmlFor={`${id}-text`}>
            <T text={label} />
          </Label>
          <Textarea
            id={`${id}-text`}
            className="min-h-36"
            maxLength={60000}
            placeholder={localise('Paste the text here')}
            value={value.text}
            disabled={Boolean(value.file)}
            onChange={(event) => {
              onChange({ text: event.target.value, file: null, document: null })
            }}
          />
        </>
      )}
      {!textOnly && (
        <>
          <Label htmlFor={`${id}-file`}>
            <T text={fileOnly ? label : 'Or upload a text document (up to 10 MB)'} />
          </Label>
          <Input
            id={`${id}-file`}
            type="file"
            accept={ACCEPT}
            disabled={Boolean(value.text.trim())}
            onChange={(event) => {
              onChange({ text: '', file: event.target.files?.[0] ?? null, document: null })
              event.currentTarget.value = ''
            }}
          />
          {value.file && (
            <p className="text-sm text-muted-foreground">
              <T text={'Selected: '} />
              {value.file.name}
            </p>
          )}
        </>
      )}
      {(value.file || value.text) && (
        <Button
          variant="ghost"
          size="sm"
          className="self-start"
          onClick={() => {
            onChange(emptyInput())
          }}
        >
          <T text={'Clear'} /> <T text={label} />
        </Button>
      )}
    </div>
  )
}

export function ContextWizard() {
  const preferredLanguage = useLanguage()
  const [stage, setStage] = useState<'documents' | 'resources' | 'analysis'>(() =>
    sessionStorage.getItem(PREPARATION_KEY) ? 'analysis' : 'documents',
  )
  const [language, setLanguage] = useState<Language>(preferredLanguage)
  const [cv, setCv] = useState<DocumentInput>(emptyInput)
  const [offer, setOffer] = useState<DocumentInput>(emptyInput)
  const [offerMode, setOfferMode] = useState<OfferMode>('none')
  const [description, setDescription] = useState('')
  const [rows, setRows] = useState<ResourceRow[]>(() => [emptyResource()])
  const [profile, setProfile] = useState<ProfileView | undefined>()
  const [profileName, setProfileName] = useState('')
  const [saveChoice, setSaveChoice] = useState<'overwrite' | 'new' | 'once'>('once')
  const [saveDialog, setSaveDialog] = useState(false)
  const [preparationId, setPreparationId] = useState<string | null>(() =>
    sessionStorage.getItem(PREPARATION_KEY),
  )
  const [snapshotId, setSnapshotId] = useState<string | undefined>()
  const [quick, setQuick] = useState(false)

  const profiles = useQuery({ queryKey: ['profiles'], queryFn: api.profiles })
  const preparation = useQuery({
    queryKey: ['preparation', preparationId],
    queryFn: () => api.preparation(preparationId ?? ''),
    enabled: preparationId !== null,
    refetchInterval: (query) => (query.state.data?.status === 'analysing' ? 1000 : false),
  })
  const selectProfile = useMutation({
    mutationFn: async (selected: ProfileView | undefined) => {
      const resources = await Promise.all(
        (selected?.resources ?? []).map(async (document) => {
          const { text } = await api.documentText(document.id)
          return {
            key: crypto.randomUUID(),
            title: document.title,
            text,
            file: null,
            document,
            originalText: text,
          }
        }),
      )
      return { selected, resources }
    },
    onSuccess: ({ selected, resources }) => {
      setProfile(selected)
      setProfileName('')
      setRows(withEmptyRow(resources))
    },
  })
  const draft = useMutation({
    mutationFn: () => api.draftJobOffer({ description, language }),
    onSuccess: (result) => {
      setOffer({ text: result.text, file: null, document: null })
    },
  })
  const analyse = useMutation({
    mutationFn: async () => {
      const cvDocument = await saveDocument('cv', 'CV', cv)
      if (cvDocument) setCv({ ...cv, document: cvDocument })
      const jobDocument =
        offerMode === 'none'
          ? null
          : await saveDocument('job_offer', 'Job offer', offer, offerMode === 'describe')
      if (jobDocument) setOffer({ ...offer, document: jobDocument })
      const resources: ResourceIn[] = []
      for (const row of rows.filter(isComplete)) {
        let document = row.document
        if (row.file) document = await api.uploadDocument('resource', row.title.trim(), row.file)
        else if (!document || row.text !== row.originalText)
          document = await api.typedDocument({
            kind: 'resource',
            title: row.title.trim(),
            text: row.text,
          })
        resources.push({ title: row.title.trim(), document_id: document.id })
        const saved = document
        setRows((current) =>
          current.map((item) =>
            item.key === row.key
              ? { ...item, document: saved, file: null, originalText: row.text }
              : item,
          ),
        )
      }
      let profileId = profile?.id
      if (saveDialog && saveChoice !== 'once') {
        const saved = await api.saveProfile(
          {
            name: saveChoice === 'overwrite' ? (profile?.name ?? '') : profileName.trim(),
            resources,
          },
          saveChoice === 'overwrite' ? profile?.id : undefined,
        )
        profileId = saved.id
        setProfile(saved)
        await profiles.refetch()
      }
      const jobMode: PrepareIn['job_mode'] =
        offerMode === 'none' ? 'none' : offerMode === 'describe' ? 'generated' : 'offer'
      return api.prepare({
        language,
        job_mode: jobMode,
        cv_id: cvDocument?.id,
        job_offer_id: jobDocument?.id,
        resources,
        profile_id: profileId,
      })
    },
    onSuccess: (view) => {
      setPreparationId(view.id)
      sessionStorage.setItem(PREPARATION_KEY, view.id)
      setStage('analysis')
      setSaveDialog(false)
    },
  })

  function restart() {
    setPreparationId(null)
    sessionStorage.removeItem(PREPARATION_KEY)
    setSnapshotId(undefined)
    setQuick(false)
    setStage('documents')
  }
  function updateRow(key: string, patch: Partial<ResourceRow>) {
    setRows((current) =>
      withEmptyRow(current.map((row) => (row.key === key ? { ...row, ...patch } : row))),
    )
  }
  const view = preparation.data
  const approved =
    snapshotId ?? (view?.status === 'approved' ? (view.snapshot_id ?? undefined) : undefined)
  if (quick || approved)
    return (
      <InterviewSetup
        key={approved ?? 'quick'}
        snapshotId={approved}
        initialLanguage={view?.language === 'en' ? 'en' : language}
        gettingToKnow={view?.job_mode === 'none'}
        onBack={restart}
      />
    )

  const validRows =
    rows.every((row) => isEmpty(row) || isComplete(row)) && rows.filter(isComplete).length <= 20
  const hasDocuments = Boolean(
    cv.text.trim() ||
    cv.file ||
    (offerMode !== 'none' && (offer.text.trim() || offer.file)) ||
    rows.some(hasContent),
  )
  const documentsReady = offerMode === 'none' || Boolean(offer.text.trim() || offer.file)
  const changed = resourcesChanged(rows, profile)
  const error = analyse.error ?? draft.error ?? selectProfile.error

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            <T text={'Prepare your interview'} />
          </h1>
          <p className="mt-2 text-muted-foreground">
            <T text={'Add your documents, check the facts, then practise out loud.'} />
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            setQuick(true)
          }}
        >
          <T text={'Quick start without documents'} />
        </Button>
      </div>
      <ol
        aria-label={localise('Preparation steps')}
        className="flex flex-wrap gap-4 text-sm text-muted-foreground"
      >
        <li className={stage === 'documents' ? 'font-semibold text-foreground' : ''}>
          <T text={'1. Documents'} />
        </li>
        <li className={stage === 'resources' ? 'font-semibold text-foreground' : ''}>
          <T text={'2. Resources'} />
        </li>
        <li className={stage === 'analysis' ? 'font-semibold text-foreground' : ''}>
          <T text={'3. Analysis and review'} />
        </li>
        <li>
          <T text={'4. Settings and microphone'} />
        </li>
      </ol>
      {stage === 'documents' && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>
                <T text={'Interview language'} />
              </CardTitle>
              <CardDescription>
                <T text={'Used for the analysis and as the default for this interview.'} />
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Select
                value={language}
                onValueChange={(value) => {
                  setLanguage(value as Language)
                  saveLanguage(value === 'en' ? 'en' : 'it')
                }}
              >
                <SelectTrigger aria-label={localise('Analysis language')}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="it">
                    <T text={'Italian'} />
                  </SelectItem>
                  <SelectItem value="en">English</SelectItem>
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>
                <T text={'Your CV'} />
              </CardTitle>
              <CardDescription>
                <T text={'Upload a file or paste its text. Scanned documents are not supported.'} />
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DocumentEditor id="cv" label="CV text" value={cv} onChange={setCv} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>
                <T text={'Job offer'} />
              </CardTitle>
              <CardDescription>
                <T
                  text={
                    'Use an offer, describe a role, or get to know a generic company in your area.'
                  }
                />
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Select
                value={offerMode}
                onValueChange={(value) => {
                  setOfferMode(value as OfferMode)
                  setOffer(emptyInput())
                  draft.reset()
                }}
              >
                <SelectTrigger aria-label={localise('Job offer source')}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">
                    <T text={'No job offer: getting-to-know interview'} />
                  </SelectItem>
                  <SelectItem value="text">
                    <T text={'Paste an offer'} />
                  </SelectItem>
                  <SelectItem value="file">
                    <T text={'Upload an offer'} />
                  </SelectItem>
                  <SelectItem value="describe">
                    <T text={'Describe a role'} />
                  </SelectItem>
                </SelectContent>
              </Select>
              {offerMode === 'describe' && (
                <>
                  <Label htmlFor="role-description">
                    <T text={'Describe the role'} />
                  </Label>
                  <Textarea
                    id="role-description"
                    maxLength={3000}
                    value={description}
                    onChange={(event) => {
                      setDescription(event.target.value)
                    }}
                  />
                  <Button
                    variant="outline"
                    className="self-start"
                    disabled={description.trim().length < 10 || draft.isPending}
                    onClick={() => {
                      draft.mutate()
                    }}
                  >
                    <T text={draft.isPending ? 'Drafting…' : 'Draft a job offer'} />
                  </Button>
                  {draft.data && (
                    <Badge variant="secondary">
                      <T text={'Drafted from your description: edit before continuing'} />
                    </Badge>
                  )}
                </>
              )}
              {offerMode !== 'none' && (offerMode !== 'describe' || draft.data) && (
                <DocumentEditor
                  id="offer"
                  label={offerMode === 'describe' ? 'Generated offer' : 'Job offer text'}
                  value={offer}
                  onChange={setOffer}
                  fileOnly={offerMode === 'file'}
                  textOnly={offerMode !== 'file'}
                />
              )}
            </CardContent>
          </Card>
          <Button
            className="self-end"
            disabled={!documentsReady || draft.isPending}
            onClick={() => {
              setStage('resources')
            }}
          >
            <T text={'Continue to resources'} />
          </Button>
        </>
      )}
      {stage === 'resources' && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>
                <T text={'Reusable resources'} />
              </CardTitle>
              <CardDescription>
                <T
                  text={
                    'Choose a profile or start a new set, then add project notes, a README or other context. Links are never followed.'
                  }
                />
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <Select
                value={profile?.id ?? 'new'}
                disabled={selectProfile.isPending || analyse.isPending}
                onValueChange={(value) => {
                  selectProfile.mutate(profiles.data?.find((p) => p.id === value))
                }}
              >
                <SelectTrigger aria-label={localise('Resource profile')}>
                  <SelectValue placeholder={localise('New profile')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="new">
                    <T text={'New profile / this interview only'} />
                  </SelectItem>
                  {profiles.data?.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {profiles.error && (
                <p role="alert" className="text-destructive">
                  <T text={'Could not load profiles.'} />
                  {profiles.error.message}
                </p>
              )}
              <fieldset
                disabled={selectProfile.isPending || analyse.isPending}
                className="flex min-w-0 flex-col gap-5"
              >
                {rows.map((row, index) => (
                  <div
                    key={row.key}
                    className="flex flex-col gap-3 rounded-lg border p-4"
                    data-testid="resource-row"
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium">
                        <T text={'Resource '} />
                        {index + 1}
                      </h3>
                      {!isEmpty(row) && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Remove resource ${index + 1}`}
                          onClick={() => {
                            setRows((current) =>
                              withEmptyRow(current.filter((item) => item.key !== row.key)),
                            )
                          }}
                        >
                          <Trash2Icon className="size-4" />
                        </Button>
                      )}
                    </div>
                    <Label htmlFor={`title-${row.key}`}>
                      <T text={'Title'} />
                    </Label>
                    <Input
                      id={`title-${row.key}`}
                      value={row.title}
                      maxLength={120}
                      onChange={(event) => {
                        updateRow(row.key, { title: event.target.value })
                      }}
                    />
                    <Label htmlFor={`content-${row.key}`}>
                      <T text={'Resource text'} />
                    </Label>
                    <Textarea
                      id={`content-${row.key}`}
                      maxLength={60000}
                      value={row.text}
                      disabled={Boolean(row.file)}
                      onChange={(event) => {
                        updateRow(row.key, { text: event.target.value })
                      }}
                    />
                    <Label htmlFor={`file-${row.key}`}>
                      <T text={'Or a text file'} />
                    </Label>
                    <Input
                      id={`file-${row.key}`}
                      type="file"
                      accept={ACCEPT}
                      disabled={Boolean(row.text.trim())}
                      onChange={(event) => {
                        updateRow(row.key, { file: event.target.files?.[0] ?? null })
                        event.currentTarget.value = ''
                      }}
                    />
                    {(row.file || row.document?.filename) && (
                      <p className="text-sm text-muted-foreground">
                        <T text={'Selected:'} />
                        {row.file?.name ?? row.document?.filename}
                      </p>
                    )}
                    {row.file && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="self-start"
                        onClick={() => {
                          updateRow(row.key, { file: null })
                        }}
                      >
                        <T text={'Clear file'} />
                      </Button>
                    )}
                  </div>
                ))}
                {rows.every(isEmpty) && (
                  <p className="text-sm text-muted-foreground">
                    <PlusIcon className="mr-1 inline size-4" />
                    <T
                      text={
                        'A new empty row appears when you fill a title and its content. Resources are optional.'
                      }
                    />
                  </p>
                )}
                {!validRows && (
                  <p className="text-sm text-amber-700">
                    <T
                      text={
                        'Each resource needs a title and text or a file. You can add at most 20.'
                      }
                    />
                  </p>
                )}
              </fieldset>
            </CardContent>
          </Card>
          <div className="flex justify-between gap-3">
            <Button
              variant="outline"
              disabled={analyse.isPending}
              onClick={() => {
                setStage('documents')
              }}
            >
              <T text={'Back to documents'} />
            </Button>
            <Button
              disabled={!hasDocuments || !validRows || analyse.isPending || selectProfile.isPending}
              onClick={() => {
                if (changed) {
                  setSaveDialog(true)
                  setSaveChoice(profile ? 'overwrite' : 'once')
                } else analyse.mutate()
              }}
            >
              <T text={analyse.isPending ? 'Submitting…' : 'Analyse documents'} />
            </Button>
          </div>
          <Dialog
            open={saveDialog}
            onOpenChange={(open) => {
              if (!analyse.isPending) setSaveDialog(open)
            }}
          >
            <DialogContent>
              <Card className="w-full max-w-lg">
                <CardHeader>
                  <DialogTitle className="font-semibold">
                    <T text={'Save your resource changes?'} />
                  </DialogTitle>
                  <DialogDescription className="text-sm text-muted-foreground">
                    <T text={'Choose how to keep this resource set.'} />
                  </DialogDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <fieldset disabled={analyse.isPending} className="flex flex-col gap-3">
                    {profile && (
                      <label className="flex gap-2">
                        <input
                          type="radio"
                          name="save-profile"
                          checked={saveChoice === 'overwrite'}
                          onChange={() => {
                            setSaveChoice('overwrite')
                          }}
                        />
                        <T text={'Overwrite'} />
                        {profile.name}
                      </label>
                    )}
                    <label className="flex gap-2">
                      <input
                        type="radio"
                        name="save-profile"
                        checked={saveChoice === 'new'}
                        onChange={() => {
                          setSaveChoice('new')
                        }}
                      />
                      <T text={'Save as a new profile'} />
                    </label>
                    <label className="flex gap-2">
                      <input
                        type="radio"
                        name="save-profile"
                        checked={saveChoice === 'once'}
                        onChange={() => {
                          setSaveChoice('once')
                        }}
                      />
                      <T text={'Use for this interview only'} />
                    </label>
                    {saveChoice === 'new' && (
                      <>
                        <Label htmlFor="profile-name">
                          <T text={'Profile name'} />
                        </Label>
                        <Input
                          id="profile-name"
                          maxLength={120}
                          value={profileName}
                          onChange={(event) => {
                            setProfileName(event.target.value)
                          }}
                        />
                      </>
                    )}
                    <div className="flex gap-2">
                      <Button
                        disabled={saveChoice === 'new' && !profileName.trim()}
                        onClick={() => {
                          analyse.mutate()
                        }}
                      >
                        <T text={analyse.isPending ? 'Submitting…' : 'Continue with analysis'} />
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setSaveDialog(false)
                        }}
                      >
                        <T text={'Cancel'} />
                      </Button>
                    </div>
                  </fieldset>
                  {analyse.error && (
                    <p role="alert" className="text-destructive">
                      {analyse.error.message}
                    </p>
                  )}
                </CardContent>
              </Card>
            </DialogContent>
          </Dialog>
        </>
      )}
      {stage === 'analysis' && (
        <>
          {(preparation.isPending || view?.status === 'analysing') && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Loader2Icon className="size-5 animate-spin" />
                  <T text={'Analysing your documents'} />
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3" aria-live="polite">
                <Progress value={(view?.analysis?.progress ?? 0) * 100} />
                <p>{view?.analysis?.message ?? 'Waiting for analysis to start'}</p>
                <p className="text-sm text-muted-foreground">
                  <T text={'You can leave this page and return to the preparation in this tab.'} />
                </p>
              </CardContent>
            </Card>
          )}
          {view?.status === 'review' && (
            <ContextReview preparation={view} onApproved={setSnapshotId} />
          )}
          {(preparation.error || view?.status === 'failed') && (
            <Alert variant="destructive">
              <AlertTitle>
                <T text={'Analysis unavailable'} />
              </AlertTitle>
              <AlertDescription>{preparation.error?.message ?? view?.error}</AlertDescription>
            </Alert>
          )}
          <Button variant="outline" className="self-start" onClick={restart}>
            <T text={'Start a new preparation'} />
          </Button>
        </>
      )}
      {error && !saveDialog && (
        <Alert variant="destructive">
          <AlertTitle>
            <T text={'Could not continue'} />
          </AlertTitle>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}
    </main>
  )
}
