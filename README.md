# shppy

## Versioning

This project derives its package version directly from Git tags via `setuptools-scm`.

The tag is the source of truth.

Preferred tag formats:

- Stable release: `v0.3.0`
- Alpha release: `v0.3.0a1`
- Beta release: `v0.3.0b1`
- Release candidate: `v0.3.0rc1`

Do not create new tags using ad-hoc suffixes such as `-alpha` or `-beta`. While some legacy tags may still be interpreted, new releases should use PEP 440 compatible tags so the published package version matches Python packaging rules.

How versions are produced:

- If the build runs on an exact tagged commit, the package version is that tag's version.
- If the build runs after a tag, the package version becomes the next development version derived from that tag.
- Local version suffixes are disabled for package builds to keep artifact versions suitable for package indexes.

Current release flow:

1. Choose the release commit.
2. Create a PEP 440 compatible tag on that commit, for example `v0.3.0` or `v0.3.0rc1`.
3. Push the tag to GitHub.
4. Publish a GitHub Release from that same tag.
5. The workflow builds and uploads distributions using the tag-derived version.

Notes:

- GitHub Actions must fetch tags for version resolution. The workflows in this repository are configured to do that.
- Building from a non-tagged commit is expected to produce a development version rather than the plain release version.
