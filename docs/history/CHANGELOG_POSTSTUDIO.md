# Post Studio Release Changelog

- Release date: 2026-04-08
- Deployed commit: `8bafbc9`
- Production target: `https://autosocial.tech` and `https://api.autosocial.tech`

## What Was Fixed
- Stabilized Post Studio specialist-grade generation on production.
- Blocked meta phrasing, editorial corridor leakage, and helper/service leakage.
- Added stronger batch diversity protection to prevent duplicate final body cores.
- Confirmed stable live generation flow after deploy.

## Niches Tested
- `psychology`
- `cosmetology`
- `apartment_renovation`
- `esoterica`
- `smm_marketing`

## Quality Checks Passed
- meta phrasing
- editorial corridor
- helper/service leakage
- duplicate body cores
- practitioner-natural voice

## Live Routes Passed
- `/`
- `/create/`
- `/create/post`

## Final Verdict
- stable production release
