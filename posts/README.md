# Posts
Author: Jovan Finesta - 2506599144

## Main Features
- Posts CRUD: frontpage feed, per-post page, create/edit/delete post
- Post and comments upvotes and downvotes
- Post tags
- Threaded comments and replies
- Comment upvotes and downvotes
- Soft-deleted comments
- Elevated moderator permissions on user posts & comments

## Extra Features
- AJAX-based dynamic fetching on posts and comments; particularly comments
- Simple loading and empty states
- Toast notifications with [SweetAlert2](https://sweetalert2.github.io/)
- Daily minimalist quote (via [custom API](https://github.com/PBP-B-Kelompok-1/minimalist-quotes-api))
- Authentication redirection
- Rich-text post and comment editor (`django-ckeditor-5`)
    - which is sanitized.
- External link warning
- Shareable post links
- Comment deep links
- Comment navigation and highlighting (on replies, comment creation)
- User avatar fallback and user profile linking
- Action menus

## Module Integrations
- Links to user profile, zen points
- Announcement preview on frontpage
- Weekly Challenge submissions through the regular Post form
- A shared `Weekly Challenge` tag identifies submissions; no per-challenge tags
- A `challenge_image` proof upload is required for tagged challenge Posts
- The Weekly Challenge `post_save` signal records the Post as a submission for
  the currently active challenge
- A user can submit only once per challenge; leaderboard scores use Post votes

## AI Declaration
AI is used to generate suggestions and complete code, along with assisting in debugs.

Logs:
- Implementing custom User model: https://www.perplexity.ai/search/92730a69-89db-4d79-af7a-c7533b95e637
- Recommendations for initial User model: https://www.perplexity.ai/search/ade14b95-b7e7-4049-872b-4f2801858ca9
- Modifying a form manually: https://chatgpt.com/s/cx_6ad4419e13dc8191a073571adb2ac78c
- XSS safety of django-ckeditor-5: https://chatgpt.com/s/cx_6ad443180b4881918f536fbb16998f82
- Upvote implementation: https://chatgpt.com/s/cx_6ad49ffc0cf08191853f8476ba9d680c
- Vibed the whole unit test (up to upvotes): https://chatgpt.com/s/cx_6adb045ea5a081919f2fb5e5cce18550
- Vibed comment recursive generation: https://chatgpt.com/s/cx_6adb045ea5a081919f2fb5e5cce18550
- Vibed comment reply form (everything about it): https://chatgpt.com/s/cx_6adb5688a21481918db10d5ef86992b7
- CSS properties for comment highlighting via url fragmenting: https://www.perplexity.ai/search/2a794c48-8a52-4678-85df-4c98fc4f00dc
- Migrating everything to Tailwind CSS (since it's required): https://chatgpt.com/s/cx_6adf6ff6f1a4819194843975cdb545dc
- ChallengePost for WeeklyChallenge: https://chatgpt.com/s/cx_6adf71719c748191b187f34f458a2983
- Unit tests (up till ChallengePost): https://chatgpt.com/s/cx_6ae214fb436c8191a430ec984cd0f784
- CKeditor sanitization: https://chatgpt.com/s/cx_6ae218dcd92c8191865528eb251f5bee
- Finish kebab styling: https://chatgpt.com/s/cx_6ae33fa3088881919dff00d41c665e61
- Sped-forward CRUD implementation, prevent updating weekly-challenge tagged posts: https://chatgpt.com/s/cx_6ae33fa3088881919dff00d41c665e61
- Announcements button on frontpage: https://chatgpt.com/s/cx_6ae3684fc8108191aab5917d438a265c
- Mobile hamburger navbar: https://chatgpt.com/s/cx_6ae36f9ffe188191b94a454652326fa3
- Tailwind migration from CDN to Django module: http://localhost:8000/post/5caabf8f-a9bb-4ec7-be67-b64c0644a9aa
