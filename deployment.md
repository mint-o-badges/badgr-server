# Deployment

This document documents how to deploy things within our systems.

## Develop / Staging

For [develop](https://develop.openbadges.education/) and [staging](https://staging.openbadges.education/) the process is quite trivial.
The version of develop is synced to the latest github build on the `develop` branch, the version of staging is synced to the latest github build on the `main` branch.
That means, to deploy something to develop or staging, simply update that branch (e.g. by merging a PR) on the remote git repository.

This applies to both `badgr-ui` and `badgr-server`.
It is achieved by using [watchtower](https://github.com/containrrr/watchtower) on those servers.
The image on the servers is set to the `develop` or `main` build from the github repository; watchtower makes sure that it's the newest build.

## Release

For [release](https://openbadges.education/) this is a bit more complicated.
This is for two reasons:
- watchtower is not meant for production use
- we have more control over what happens / which version is deployed that way.

To deploy, follow these steps (note that you have to do them for both `badgr-server` *and* `badgr-ui`, if you want to deploy both):
- Checkout your desired commit. Ideally this is the last commit on `main` (run `git checkout main && git pull`), but it can also be any other commit
- Tag a version in the format `v*.*.*`, e.g. `v1.2.34`. To do this, run `git tag v1.2.34` in your local terminal
- Wait for the [Github action](https://github.com/mint-o-badges/badgr-server/actions) to complete
- Go to the server (`ssh ubuntu@openbadges.education`)
- Navigate to the `badgr-server` directory (`cd docker/badgr-server/`)
- Open the `docker-compose.yml` (`vim docker-compose.yml`)
- Search for the api image version (`/image: ghcr.io/mint-o-badges/badgr-server`)
- Change the version (the part after the last `:`) to the name you gave your tag (e.g. `v1.2.34`)
- Update the container by running `docker compose up -d`
- Validate that the correct version is deployed by checking the [imprint](https://openbadges.education/public/impressum)
% TODO: Something isn't working there yet, maybe because some critical information is not persisted between versions of the docker image. Maybe check what the old script did?
