# 0022: Profiles and CV checks without an interview, and what deleting them removes

- Status: Accepted
- Date: 2026-11-12

## Context

A profile could be created only in the documents step of the new-interview wizard, and a first CV
check could run only in its final step. A CV check therefore required interview settings
(type, difficulty, duration) that it does not use. The backend never had this dependency: profile
CRUD, preparations, approval and CV review take no interview, and
[the context proposal](../proposals/2026-11-context-evaluation-reports.md#3-cv-review-new)
describes the CV review as available before or without an interview.

Deletion was incomplete. A CV check could not be deleted at all. Deleting a profile removed its
row and resource links, but its documents and uploaded files stayed in the data volume with no
owner, so a CV left the machine only through **Delete all my data**.

Reports did not record which profile they belonged to. Interviews stored the profile they were
prepared with; CV reviews, keyed by the approved context, did not.

## Decision

**Standalone flows.** Profiles have their own creation page. A CV check starts from a saved
profile with a CV, or from documents added for that check, which can be saved as a profile at the
same time. It continues with the same analysis review as the wizard (target role, area and facts),
then approves the context and starts the review. The preparation and the approved context are
identified in the URL, so no client-side draft is involved. The wizard keeps every profile choice
it had and uses the same components.

**Ownership.** Every report records the saved profile it belongs to, in a database column outside
the assessed content. Interview reports take it from the interview; CV reviews take it from the
request. The link survives the deletion of the profile. Saving a CV check as a profile makes the
new profile the owner of the check's versions that have none.

**Deleting a CV check** removes every version of its report and its finished review jobs. When no
interview and no other report uses the approved context, the context, the preparations that
approved it and their jobs go too. Documents are then deleted when nothing else refers to them.
A saved profile keeps its documents, so the check can be run again from it.

**Deleting a profile** removes the profile and its resource links. Its interviews, their reports
and its CV checks stay, with the contexts and documents they need to remain readable and to be
assessed again. Preparations of the profile whose context nothing uses are deleted, except those
still being analysed, and so are the contexts and documents only they kept.

**Document cleanup** considers only the documents of the deleted records, never the whole volume:
an upload that nothing refers to yet may belong to work in progress. A candidate document goes
when no profile, preparation or approved context refers to it. Earlier documents with the same
uploaded file, such as the original of an edited text, go with it; newer ones stay. An uploaded
file is deleted when no remaining document uses it.

## Consequences

- CV checks no longer need interview settings, and profiles can be prepared before any interview.
- Migration 0009 adds the report owner. It assigns existing interview reports to their interview's
  profile, and existing CV reports to the profile of the preparations that approved their context
  when exactly one profile did.
- Identical approved content is still one context. Two profiles with the same documents share its
  CV check history, and its versions may belong to different profiles.
- Cached model extractions are keyed by request hash, not by document, so deleting documents
  does not remove them. **Delete all my data** still does.
- Deleting a check while the wizard of another tab shows the same approved context makes that
  wizard fail when it starts the interview; the user analyses the documents again.

## Alternatives considered

- **Keep creation in the wizard and only add links to it**: CV checks would still require
  interview settings.
- **A client-side draft for the CV check, like the wizard**: the server already holds the state,
  and an address can be reopened after a reload or from another tab.
- **Delete documents globally when nothing refers to them**: uploads of a preparation in progress
  have no reference until the analysis starts and would be lost.
- **Keep reports immutable and record ownership in a separate table**: one nullable column is
  enough while a report has at most one owner.
