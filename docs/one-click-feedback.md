# One-click feedback endpoint

The email feedback buttons can be fully automated with a tiny Cloudflare Worker.
Clicking a button opens the Worker URL once; the Worker verifies the signed link
and creates a GitHub issue labeled `paper-feedback`. Daily GitHub Actions reads
these issues and applies the feedback automatically.

## GitHub secrets

Set these repository secrets for the daily/test workflows:

- `FEEDBACK_ENDPOINT`: your deployed Worker URL, for example `https://paper-feedback.example.workers.dev`
- `FEEDBACK_SECRET`: a long random shared secret used to sign feedback links

## Worker secrets

Deploy `tools/feedback-worker.js` to Cloudflare Workers and configure:

- `FEEDBACK_SECRET`: the same value as the GitHub repository secret
- `GITHUB_REPOSITORY`: `owner/repo`, for example `Agitw/zotero-arxiv-daily`
- `GITHUB_TOKEN`: a fine-grained GitHub token with Issues read/write access for this repository

## Flow

1. The daily email renders signed links for `important`, `read`, and `not_interested`.
2. Clicking a link sends the signed payload to the Worker.
3. The Worker verifies the HMAC signature.
4. The Worker creates an issue labeled `paper-feedback`.
5. The next daily run reads open `paper-feedback` issues and adjusts ranking.
