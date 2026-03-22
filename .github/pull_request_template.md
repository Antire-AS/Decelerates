## What does this PR do?

<!-- 1–3 bullet points -->

## Branch target checklist

- [ ] **Targeting `staging`** — for features and fixes. CI (tests + lint) runs automatically.
  After merge, staging deploys and smoke-tests at `/ping`. Validate manually before opening PR to `main`.
- [ ] **Targeting `main`** — only after staging has been validated. CI runs again.
  After merge, prod deploys and smoke-tests at `/ping`.

## Test plan

<!-- What did you test locally / what should reviewers check? -->
