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
