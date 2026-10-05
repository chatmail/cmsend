
## [0.6.0] - 2026-10-05

### Fixes

- update to core 2.62 and fix various small issues.

- comment cleanup.


## [0.5.0] - 2026-07-28

- use newer deltachat-rpc version (2.57).


## [0.4.4] - 2026-07-28

- support setup-contact as well as group invite links.

- adapt to chatmail/workflows release standards.

- adopt shared CI from chatmail/workflows (ruff lint+format, build)
  and release via PyPI trusted publishing on v* tags

- fix "cmsend -l" crashing with AttributeError when listing chat
  members

- `main()` accepts an optional argv list so tests can invoke it

- fix pyproject description (was copied from cmping)

## 0.4.2

- improve output on "cmsend -l" to show members of each chat

## 0.4.1

- add warning

## 0.4.0 tagged chats

- added "-t" tagged chats option, so that "--join" can be accompanied by "-t"

- added "cmsend -l" to list all tagged chats


## 0.3.2

- fixed README

## 0.3.1

- fixed README

## 0.3.0

- added more options

## 0.1.0

- initial release
