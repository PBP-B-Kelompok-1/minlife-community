# Weekly Challenge TODO

This checklist tracks work needed to keep the Weekly Challenge module aligned with
the Mid-Term Django project rubric and ready for integration, deployment, and live
demonstration.

## Completed

- [x] Define Challenge, ChallengeTask, and ChallengeSubmission models.
- [x] Add database constraints for valid date ranges, task day ranges, unique task days,
      one submission per Post, and one submission per user per Challenge.
- [x] Add transactional Challenge creation with its Badge, system Tag, and task rows.
- [x] Add current-Challenge and submission lookup services.
- [x] Add permanent Badge awarding based on net Post score.
- [x] Add Challenge form validation, native date inputs, overlap validation, and the
      seven-task limit.
- [x] Add Challenge create, read, update, and delete routes.
- [x] Add Challenge directory filtering, search, pagination, and leaderboard sorting.
- [x] Add moderator permission checks to management routes.
- [x] Show the create button to users with `weeklychallenge.add_challenge`, including
      superusers.
- [x] Add responsive Tailwind templates and reusable Challenge components.
- [x] Add HTMX task-row controls, Challenge filtering, and submission-list updates.
- [x] Add `Post` and `Vote` signals for submissions and Badge evaluation.
- [x] Register signals through `WeeklychallengeConfig.ready()`.
- [x] Add focused tests for models, services, forms, views, permissions, HTMX behavior,
      signals, and Badge persistence.
- [x] Enforce one Badge per Challenge and preserve earned Badges after submission or
      Challenge deletion.
- [x] Add shared HTMX request detection, redirects, event triggers, canonical URL
      headers, CSRF handling, indicators, and accessible error feedback.
- [x] Add HTMX list/detail navigation, filter/search updates, leaderboard updates,
      create/edit form swaps, and delete confirmation modal with non-HTMX fallbacks.

## Highest-priority implementation

### Posts and Challenge integration

- [ ] Pass the active Challenge into the Posts form instead of relying on the legacy
      static `Weekly Challenge` Tag.
- [ ] Let users explicitly select the active Challenge when creating a submission.
- [ ] Exclude system Challenge Tags from the general-purpose Tag selector.
- [ ] Validate that a selected Challenge is currently open before saving the Post.
- [ ] Require `challenge_image` when a Challenge is selected.
- [ ] Attach the selected Challenge's dynamic Tag after the Post is saved.
- [ ] Preserve the Challenge Tag when a Post is edited and ordinary tags are replaced.
- [ ] Keep the second `post.save()` after `form.save_m2m()` so the `post_save` signal
      sees the completed tag set.
- [ ] Add end-to-end Posts tests covering valid submission, missing image, inactive
      Challenge, duplicate submission, and Post editing.

### Challenge deletion policy

- [x] A Challenge has exactly one Badge, and a Badge belongs to at most one Challenge.
- [x] Deleting a Challenge deletes its submissions but preserves its Badge and all
      previously earned UserBadge records.
- [x] Deleting a submission or its Post does not revoke an earned UserBadge.

### Authorization consistency

- [x] Ensure every management route checks the intended rule server-side, not only
      through hidden buttons.
- [x] Test anonymous users, normal users, users with individual permissions,
      Moderator-group users, and superusers.
- [x] Ensure unauthorized responses provide an understandable 403 or login flow.

## Rubric: CRUD and MVT quality

- [ ] Test successful and invalid POST requests for Challenge creation.
- [ ] Test successful and invalid POST requests for Challenge editing.
- [ ] Test confirmation and failure behavior for Challenge deletion.
- [ ] Test Challenge detail, empty states, unknown IDs, and missing tasks.
- [ ] Test list filters for open, upcoming, past, and all Challenges.
- [ ] Test title search, pagination boundaries, and leaderboard score/newest sorting.
- [ ] Review all management views for explicit error handling and transaction safety.
- [ ] Confirm the templates use the shared base template and design-system classes.

## Rubric: HTMX and responsive interactivity

- [x] Decide whether create, edit, and delete should also use HTMX or whether the
      current full-page flow is sufficient for the target rubric score. Decision: Use HTMX to go the extra mile
- [ ] Test HTMX requests and ordinary browser requests separately where behavior differs.
- [ ] Verify task-row controls preserve management-form values and form data.
- [ ] Test the mobile layout at the target presentation viewport.
- [ ] Test keyboard focus, labels, error display, and accessible loading/update states.
- [ ] Confirm the pinned HTMX CDN dependency is available in the deployed environment.

## Rubric: testing and coverage

- [ ] Run the complete project test suite, not only `weeklychallenge posts`.
- [ ] Measure coverage for the full module and the cross-app Posts integration.
- [ ] Raise Weekly Challenge source coverage to at least 90% where practical.
- [ ] Add negative tests for invalid permissions, invalid dates, duplicate tasks,
      duplicate submissions, inactive Challenges, and negative vote scores.
- [ ] Add a browser-level or functional demonstration test if required by the final
      grading interpretation.
- [ ] Remove or document the non-blocking missing `staticfiles/` test warning.

Recommended focused validation:

```powershell
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py test weeklychallenge posts
.\venv\Scripts\python.exe -m coverage run --source=weeklychallenge,posts manage.py test weeklychallenge posts
.\venv\Scripts\python.exe -m coverage report -m
git diff --check
```

## Rubric: documentation and project submission

- [x] Update the root README with the final module list, ownership, user roles,
      application description, setup instructions, and deployment link.
- [x] Document the actual public API or external mock API source and implementation.
- [x] Verify whether Firebase Cloud Messaging is implemented; do not list it as
      completed if it is only planned.
- [x] Add the required Figma/design link and confirm the deployed UI matches it.
- [ ] Add an AI-use disclosure covering tools, purpose, manual review, and limitations.
- [ ] Add screenshots or a short GIF if required for the strongest documentation score.

## Rubric: deployment and live demonstration

- [ ] Verify the PWS deployment serves the landing page and `/weeklychallenge/` routes.
- [ ] Run migrations and verify required permissions and the `Moderator` Group in the
      deployed environment.
- [ ] Confirm media uploads work for Challenge submissions.
- [ ] Seed enough initial project data for the project-wide deployment requirement.
- [x] Test the deployed flow with a moderator, normal user, and superuser.
- [x] Demonstrate Challenge creation, task HTMX controls, Post submission, leaderboard
      updates, voting, Badge awarding, and Badge persistence after vote removal.
- [x] Demonstrate unauthorized management access and the Challenge directory filters.
- [ ] Prepare fallback demo data in case the deployed database is unavailable.

## Rubric: Git collaboration evidence

- [x] Keep implementation, tests, documentation, and cross-app integration in
      focused descriptive commits.
- [x] Use independent branches for member work.
- [x] Open Pull Requests for integration changes.
- [x] Obtain peer review before merging.
- [x] Preserve test and validation results in the relevant Pull Request descriptions.
- [x] Avoid one large deadline commit; ensure the history shows incremental progress.

## Known concerns to resolve or explicitly accept

- [ ] Dynamic Challenge Tags and the legacy static `Weekly Challenge` Tag currently
      represent two different concepts in Posts.
- [ ] The `post_save` submission signal depends on the Post being saved after M2M tags
      are assigned.
- [ ] `Badge.__str__` should be implemented if the Users module requires readable Badge
      values in admin or templates.
- [ ] `Vote.__str__` should safely handle comment Votes with no Post.
- [ ] Challenge overlap is protected by form validation but not by a database-level
      exclusion constraint against concurrent creation.
- [x] Challenge deletion preserves protected Badges and permanent UserBadge history.
