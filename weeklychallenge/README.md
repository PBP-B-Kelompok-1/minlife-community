# Weekly Challenge

The Weekly Challenge module lets moderators publish a short, structured
challenge and lets community members share their progress through normal Posts.
This document explains the feature from the outside in: first what a user sees,
then how Django models, forms, views, services, and signals work together.

Module owner: Clement Kevin Tanadi (2506632892).

## Start here: the idea in one paragraph

A moderator creates a challenge with a title, an explanation of the problem, a
goal, a starting date, and up to seven daily tasks. During the seven-day
challenge window, a user creates a regular Post and adds the shared
`Weekly Challenge` tag. The Post must include an image as evidence. Django then
automatically records that Post as the user's submission. The submission
appears on the leaderboard, where its score is the sum of its votes:
`upvotes - downvotes`. When the score reaches the challenge's threshold, the
user receives a permanent badge.

There is deliberately no separate "submission" form. A challenge submission is
an ordinary Post with a special tag, which keeps the community's posting
experience consistent.

## Glossary

| Term | Meaning |
| --- | --- |
| Challenge | The moderator-created activity, including its description, dates, threshold, and badge. |
| Challenge task | One daily activity inside a challenge. Tasks are numbered from day 1 through day 7. |
| Active challenge | A challenge whose seven-day date window includes today. |
| Submission | A `ChallengeSubmission` row connecting one Post and one user to one challenge. |
| Shared challenge tag | The single Posts tag named `Weekly Challenge`. It identifies challenge Posts. |
| Net score | The Post's upvotes minus its downvotes. In the database this is the sum of Vote values (`1` or `-1`). |
| Badge | The achievement created for a challenge and awarded when a submission reaches the threshold. |

## What a visitor can do

### The active challenge page

The route `/weeklychallenge/` shows the current challenge. It contains:

1. The challenge title, background, description, and goal.
2. A seven-day timeline, with the current day highlighted.
3. The task for the current day, when one exists.
4. A link to create a Post and share progress.
5. A feed of submissions, ordered by net score and then submission time.

An unauthenticated visitor is asked to log in before joining. An authenticated
user who has already submitted sees a message instead of another submission
link. This is a user-interface convenience only; the database constraint also
prevents duplicate submissions.

### The challenge directory

The directory at `/weeklychallenge/list/` is useful when there are several
challenges. It can filter by open, upcoming, or past status, search by title,
and paginate results. Each challenge has a detail page. Upcoming challenges
are shown as teasers to ordinary users so that a moderator can prepare content
without exposing future tasks too early.

The leaderboard supports sorting by:

- **Score:** highest net score first, then newest submission.
- **Newest:** most recently created submission first.

### Moderator management

Users with the appropriate Django permission can:

- Create a challenge.
- Add, edit, reorder, and delete daily task rows.
- Edit challenge details and tasks.
- Open a confirmation page or modal before deleting a challenge.

The server checks permissions on every management request. Hiding a button in a
template is not treated as authorization.

## The complete lifecycle

### 1. A moderator creates a challenge

The moderator submits the challenge form and its inline task formset. The form
contains:

- `title`
- `background`
- `description`
- `goal`
- `upvote_threshold`
- `week_start`

The badge and creator are intentionally not editable form fields. They are
assigned by the service layer. `ChallengeForm.clean()` rejects a start date
whose seven-day window overlaps another challenge.

`create_challenge()` in `weeklychallenge/services.py` runs the operation inside
`transaction.atomic()`:

1. Save the validated challenge data without committing it.
2. Create a Badge named `<challenge title> Badge`.
3. Set `created_by` to the moderator.
4. Save the Challenge.
5. Attach the validated task formset to the new Challenge.

If any part fails, the transaction rolls back instead of leaving a challenge
without its badge or tasks. New code should call `create_challenge()` rather
than calling `Challenge.objects.create()` directly.

### 2. Django decides whether the challenge is active

`ChallengeQuerySet.current()` treats a challenge as active when:

```text
week_start <= today <= week_start + 6 days
```

The model exposes the same end date through the `week_end` property and the
same state through `is_open`. The service function
`get_current_challenge()` is the shared lookup used by other modules.

This design stores only one start date instead of storing both a start and end
date. The end date is derived from the fixed seven-day rule, so the two dates
cannot drift apart.

The form prevents overlapping seven-day windows. This is application-level
validation; it is not a database exclusion constraint for concurrent writes.

### 3. A user creates a normal Post

The user follows the Posts create link. The Posts form handles the submission,
not a Weekly Challenge view. To become a challenge submission, the Post must:

1. Include the `Weekly Challenge` tag.
2. Include an uploaded `challenge_image`.
3. Be saved while a challenge is active.

The image is stored under `MEDIA_ROOT/challenge_images/`. The Posts form also
checks that uploaded images are no larger than 5 MB and no larger than 25
megapixels. These limits prevent unexpectedly large uploads from consuming
storage or memory.

When editing an existing challenge Post, the shared challenge tag cannot be
added or removed. This protects the meaning of the existing
`ChallengeSubmission` record. The edit flow must also preserve the tag when
calling `form.save_m2m()` or `tags.set()`.

### 4. A Post becomes a submission through a signal

The `post_save` handler in `weeklychallenge/signals.py` runs after a Post is
saved. It:

1. Checks whether the Post has the exact shared tag.
2. Finds the current challenge.
3. Calls `ChallengeSubmission.objects.get_or_create()`.

The tag is a Many-to-Many relation, so it is not available during the first
`post.save()` call. The correct Posts flow is:

```text
post.save()
form.save_m2m()
post.save()  # lets post_save see the completed tag set
```

The second save is important. Without it, the signal may run before the tag is
attached and no submission will be recorded.

`get_or_create()` and the database uniqueness constraint make the operation
idempotent: repeating the signal does not create multiple rows for the same
user and challenge. An `IntegrityError` is also handled so an attempted
duplicate does not make the original Post save fail.

### 5. The leaderboard calculates progress

`ChallengeSubmission` links:

```text
ChallengeSubmission
  ├── challenge -> Challenge
  ├── post      -> Posts.Post
  └── user      -> Users.User
```

The leaderboard query annotates every submission with the sum of the related
Post's Vote values. An upvote has value `1`; a downvote has value `-1`.
Therefore, five upvotes and two downvotes produce a score of `3`.

The page uses `select_related()` and database aggregation so it can load the
related Post and user without manually querying each submission in a loop.

### 6. Voting awards a permanent badge

When a Vote is created or deleted, the Vote signal re-fetches its Post and calls
`award_badge_if_eligible(post)`. The service:

1. Finds the Post's `challenge_submission`.
2. Compares `post.get_vote_count()` with the challenge threshold.
3. Calls `UserBadge.objects.get_or_create()` when the threshold is met.

The award operation is also atomic and idempotent. A badge is not removed when
the score later falls below the threshold, and it remains in the user's
history if the submission Post is deleted.

Vote signals ignore comment Votes because a comment Vote has no `post_id`.
This is why Vote changes must use `save()` and `delete()` rather than
`QuerySet.update()` or `bulk_create()`: bulk operations do not emit the model
signals that trigger badge evaluation.

## Data model and constraints

### `Challenge`

Defined in `weeklychallenge/models.py`, a Challenge stores the title,
background, description, goal, threshold, start date, creator, and its Badge.
The nullable `tag` relation is retained only for legacy data compatibility.
New challenges use the shared Posts tag instead.

### `ChallengeTask`

Each task belongs to one Challenge and has a `day_number`, title, and optional
description. The model enforces:

- Day numbers must be between 1 and 7.
- A challenge cannot contain two tasks for the same day.
- Tasks are returned in day-number order.
- Deleting a challenge deletes its task rows.

### `ChallengeSubmission`

Each Post can be associated with at most one submission because `post` is a
One-to-One relation. A database constraint also enforces one submission per
user per challenge. Deleting the Challenge deletes its submission rows;
deleting a Post deletes its submission row as well.

### Badge and UserBadge

The Users application owns `Badge` and `UserBadge`. A Challenge has one Badge,
and the service creates the Badge during challenge creation. `UserBadge` records
the user, badge, and earning time. The deletion policy preserves the Badge and
earned history when a Challenge is deleted.

## How the code is organized

| File | Responsibility |
| --- | --- |
| `weeklychallenge/models.py` | Challenge, task, and submission models; query helpers; constraints. |
| `weeklychallenge/forms.py` | Challenge form and seven-task inline formset. |
| `weeklychallenge/services.py` | Transactional creation, active-challenge lookup, submission lookup, and badge awarding. |
| `weeklychallenge/signals.py` | Converts tagged Posts into submissions and re-evaluates badges after Vote changes. |
| `weeklychallenge/views.py` | Page rendering, filtering, pagination, CRUD, permission checks, and HTMX endpoints. |
| `weeklychallenge/urls.py` | Namespaced URLs for the directory, detail, CRUD, and partial endpoints. |
| `weeklychallenge/apps.py` | Registers signals once Django has loaded the Post and Vote models. |
| `templates/challenges/page.html` | Active challenge landing page and submission feed. |
| `templates/challenges/list.html` | Challenge directory shell. |
| `templates/challenges/detail.html` | Challenge detail and leaderboard page. |
| `templates/challenges/form.html` | Full-page moderator create/edit form. |
| `templates/challenges/components/` | Reusable HTMX fragments and non-JavaScript form pieces. |
| `posts/models.py` | Post, Tag, and Vote data used by the challenge. |
| `posts/forms.py` | Challenge image validation and shared-tag rules. |

## HTMX and the non-JavaScript fallback

The module uses HTMX 2.0.4 to make common interactions feel faster without
building a separate frontend application. Examples include:

- Filtering and searching the directory.
- Changing leaderboard sort and pagination.
- Adding or removing task form rows.
- Loading the delete confirmation modal.
- Swapping validation errors into create/edit forms.

The server still owns the behavior. Each HTMX endpoint has an ordinary HTML
equivalent, including form `action` URLs, links, POST handling, and redirects.
This means the feature remains usable when JavaScript is disabled, HTMX fails
to load, a screen reader follows a normal link, or a browser restores history.

Boosted navigation and history-restore requests receive full pages rather than
fragments. That design prevents a fragment from being inserted where a complete
document is expected and keeps reload and back-button behavior predictable.

HTMX responses use canonical URLs, `HX-Push-Url`, `HX-Redirect`, CSRF handling,
loading indicators, and the `challengeChanged` event where appropriate.

## Permissions and safety choices

The module uses Django permissions:

- `weeklychallenge.add_challenge` allows creation.
- `weeklychallenge.change_challenge` allows editing and task management.
- `weeklychallenge.delete_challenge` allows deletion.

The views check authentication and permissions server-side. Anonymous HTMX
requests receive an `HX-Redirect` to login; ordinary requests use the normal
login or permission flow. A moderator button is displayed only when the user
has the relevant permission, but the view checks are the actual protection.

Deletion is intentionally a POST-only action. A GET request displays a
confirmation page or modal, and only the confirmed POST deletes the challenge.
If another protected relationship prevents deletion, the view returns an
understandable error instead of silently reporting success.

## Important design choices

### One shared tag instead of one tag per challenge

All new challenge Posts use `Weekly Challenge`. A tag per challenge would
require creating and maintaining extra Tags and would make the Post form
harder to understand. The active challenge at save time determines which
challenge receives the submission.

The trade-off is that an old challenge tag is not enough to identify a
historical challenge by itself. The `ChallengeSubmission` row stores that
historical relationship, while the tag remains the user-facing entry point.

### Submission through Posts instead of a second form

Users already know how to create a Post, and Posts already provide title,
content, tags, votes, and comments. Reusing that model avoids duplicate
content and lets the normal Post page remain the source of truth.

### Permanent badges

The badge is an achievement, not a live scoreboard label. Once earned, it stays
earned even if votes change or the evidence Post is removed. This makes the
profile history meaningful and avoids surprising users by removing an award
they already achieved.

### Derived seven-day end date

Only `week_start` is stored. `week_end` is calculated as six days after it.
This keeps the fixed seven-day rule in one place and lets the model, queryset,
form validation, and templates use the same definition of an active challenge.

### Service layer for cross-model actions

Creating a challenge touches a Challenge, Badge, and task formset. Awarding a
badge touches a Post, ChallengeSubmission, and UserBadge. These operations live
in `services.py` so views and signals stay small and the transaction/idempotency
rules are reusable.

## Setup and validation

From the project root:

```powershell
python manage.py check
python manage.py test weeklychallenge posts
python manage.py makemigrations --check --dry-run
git diff --check
```

Before merging changes that cross module boundaries, run the complete project
test suite as well. Focused Weekly Challenge tests cover models, services,
forms, permissions, filtering, rendering, updates, deletion, badge
persistence, signals, and HTMX interactions.

The applications `users`, `posts`, and `weeklychallenge` must be present in
`INSTALLED_APPS`, and their migrations must be applied. Uploaded challenge
images also require working `MEDIA_ROOT` and `MEDIA_URL` settings in local and
deployed environments.

## Implementation status

- [x] Models, relationships, constraints, and migrations.
- [x] Transactional challenge creation with badges and tasks.
- [x] Active-challenge and submission lookup services.
- [x] Challenge form validation, date picker, overlap validation, and seven-task limit.
- [x] Challenge directory, detail page, leaderboard, CRUD, and permission checks.
- [x] Responsive Tailwind templates and reusable challenge components.
- [x] HTMX filtering, search, pagination, navigation, task-row controls, forms,
      and delete confirmation.
- [x] Full-page fallbacks for all CRUD and navigation flows.
- [x] Post and Vote signals for submissions and badge evaluation.
- [x] Focused tests for the module and Posts integration.

## Known follow-ups

- The overlap check is form-level validation, not a database-level exclusion
  constraint for concurrent challenge creation.
- `post_save` submission creation depends on saving the Post after its M2M tags
  have been assigned.
- `Badge.__str__` should return the badge name if the Users admin or templates
  require a readable value.
- `Vote.__str__` should safely represent comment Votes, which do not have a
  Post.
- Manual browser checks are still needed for responsive layout, keyboard focus,
  screen readers, JavaScript-disabled fallback, and deployment.
