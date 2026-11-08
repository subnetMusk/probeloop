/** Live captions over the call: what is being said right now. */
export function Captions({ speaker, text }: { speaker: string; text: string }) {
  if (!text.trim()) return null
  // Keep the tail: captions show the latest words, not the whole answer.
  const shown = text.length > 220 ? `…${text.slice(-220).replace(/^\S*\s/, '')}` : text
  return (
    <div
      className="pointer-events-none mx-auto w-full max-w-3xl rounded-xl bg-black/70 px-4 py-2.5 text-center text-base leading-relaxed text-white backdrop-blur"
      data-testid="captions"
    >
      <span className="mr-2 text-xs font-medium tracking-wide text-zinc-400 uppercase">
        {speaker}
      </span>
      {shown}
    </div>
  )
}
