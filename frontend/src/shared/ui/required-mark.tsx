/** The visual mark of a required field. Assistive technologies read the field's `required`. */
export function RequiredMark() {
  return (
    <span aria-hidden="true" className="text-highlight-text">
      *
    </span>
  )
}
