import { Link } from '@tanstack/react-router'

import { useMessages } from '@/shared/i18n'
import { shellMessages } from './messages'

const AUTHOR = 'https://github.com/subnetMusk/'

export function Footer() {
  const t = useMessages(shellMessages)
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-6 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>
          {t.footer.madeBy}{' '}
          <a
            href={AUTHOR}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-foreground underline-offset-4 hover:underline"
          >
            subnetMusk
          </a>
        </p>
        <Link to="/accessibility" className="underline-offset-4 hover:underline">
          {t.footer.accessibility}
        </Link>
      </div>
    </footer>
  )
}
