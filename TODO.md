# Project TODO

## Project-wide responsive CSS and layout

- [ ] Implement a mobile navigation experience in
      `templates/components/navbar.html`; the current navigation is hidden below
      600px without a replacement menu.
- [ ] Fix the malformed closing anchor in the shared navbar title and verify the
      navbar markup at mobile, tablet, and desktop widths.
- [ ] Standardize responsive breakpoints between shared CSS and Tailwind utility
      classes. The project currently mixes a 600px media query with Tailwind's
      `sm` breakpoint.
- [ ] Review shared and module-specific layouts for narrow-screen overflow,
      including navbar controls, challenge actions, pagination, forms, post
      controls, and user profile sections.
- [ ] Verify shared modal behavior on short and narrow viewports. Modal content
      should remain usable when it exceeds the available viewport height.
- [ ] Run responsive browser checks for representative viewport sizes:
      375px, 640px, 768px, 1024px, and 1440px.
- [ ] Update module-specific responsive checklists after the shared fixes are
      implemented, and document any intentional module-specific exceptions.

## Weekly Challenge project-wide follow-up

These items were moved from `weeklychallenge/TODO.md` because they affect the
whole project rather than only the Weekly Challenge implementation.

### Testing and coverage

- [ ] Run the complete project test suite, not only `weeklychallenge posts`.
- [ ] Measure coverage for the full module and the cross-app Posts integration.
- [ ] Raise Weekly Challenge source coverage to at least 90% where practical.
- [ ] Add a browser-level or functional demonstration test if required by the
      final grading interpretation.
- [ ] Remove or document the non-blocking missing `staticfiles/` test warning.

Recommended focused validation:

```powershell
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py test weeklychallenge posts
.\venv\Scripts\python.exe -m coverage run --source=weeklychallenge,posts manage.py test weeklychallenge posts
.\venv\Scripts\python.exe -m coverage report -m
git diff --check
```

### Documentation and project submission

- [x] Update the root README with the final module list, ownership, user roles,
      application description, setup instructions, and deployment link.
- [x] Document the actual public API or external mock API source and
      implementation.
- [x] Verify whether Firebase Cloud Messaging is implemented; do not list it as
      completed if it is only planned.
- [x] Add the required Figma/design link and confirm the deployed UI matches it.
- [ ] Add an AI-use disclosure covering tools, purpose, manual review, and
      limitations.
- [ ] Add screenshots or a short GIF if required for the strongest
      documentation score.

### Deployment and live demonstration

- [ ] Verify the PWS deployment serves the landing page and
      `/weeklychallenge/` routes.
- [ ] Run migrations and verify required permissions and the `Moderator` Group
      in the deployed environment.
- [ ] Confirm media uploads work for Challenge submissions.
- [ ] Seed enough initial project data for the project-wide deployment
      requirement.
- [x] Test the deployed flow with a moderator, normal user, and superuser.
- [x] Demonstrate Challenge creation, task HTMX controls, Post submission,
      leaderboard updates, voting, Badge awarding, and Badge persistence after
      vote removal.
- [x] Demonstrate unauthorized management access and the Challenge directory
      filters.
- [ ] Prepare fallback demo data in case the deployed database is unavailable.

### Git collaboration evidence

- [x] Keep implementation, tests, documentation, and cross-app integration in
      focused descriptive commits.
- [x] Use independent branches for member work.
- [x] Open Pull Requests for integration changes.
- [x] Obtain peer review before merging.
- [x] Preserve test and validation results in the relevant Pull Request
      descriptions.
- [x] Avoid one large deadline commit; ensure the history shows incremental
      progress.
