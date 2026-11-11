// Preserve the notices of production packages that are bundled into the browser application.
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const lock = JSON.parse(readFileSync(path.join(root, 'package-lock.json'), 'utf8'))
const sections = []
const missing = []

for (const [relative, entry] of Object.entries(lock.packages).sort(([a], [b]) =>
  a.localeCompare(b),
)) {
  if (!relative.startsWith('node_modules/') || entry.dev || entry.link) continue
  const directory = path.join(root, relative)
  if (!existsSync(directory)) continue // Optional packages for another operating system.
  const metadata = JSON.parse(readFileSync(path.join(directory, 'package.json'), 'utf8'))
  const files = readdirSync(directory, { withFileTypes: true })
    .filter((file) => file.isFile() && /^(licen[cs]e|copying|notice)(\.|$)/i.test(file.name))
    .map((file) => file.name)
    .sort()
  let text = files
    .map((name) => `${name}\n${readFileSync(path.join(directory, name), 'utf8').trim()}`)
    .join('\n\n')
  if (!text) {
    const fallback = path.join(root, '../licenses', `${metadata.name}-${metadata.version}-MIT.txt`)
    if (existsSync(fallback)) text = readFileSync(fallback, 'utf8').trim()
  }
  if (!text) missing.push(`${metadata.name}@${metadata.version}`)
  sections.push(
    `${metadata.name}@${metadata.version}\nLicense: ${metadata.license ?? entry.license ?? 'See upstream'}\n\n${text}`,
  )
}

if (missing.length)
  throw new Error(`Production packages without licence files: ${missing.join(', ')}`)
writeFileSync(
  path.join(root, 'dist/assets/THIRD_PARTY_LICENSES.txt'),
  `Third-party production dependencies\n\n${sections.join('\n\n' + '='.repeat(72) + '\n\n')}\n`,
)
