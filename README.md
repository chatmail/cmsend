# cmsend: chatmail sendmail tool for end-to-end encrypted messages

**WORK IN PROGRESS: this is more an explorative study for now**

To install use:

    uv tool install cmsend

To send and receive from a single chatmail relay:

    cmsend --init nine.testrun.org   # <-- substitute with the domain you want to set as origin

To setup a tagged chat using an invite link:

    cmsend -t LOG --join "INVITELINK"       # <-- quotes are neccessary because links contain "&"

To send a message to a tagged chat:

    echo "hello" | cmsend -t LOG

To list all chats with tags:

    cmsend -l

To send a message to a tagged chat with an attachment:

    cmsend -t LOG -m "here is the file" -a README.md

To show help:

    cmsend -h


## Developing / Releasing cmsend

1. clone the git repository at https://github.com/chatmail/cmsend

2. install 'cmsend' in editing mode: `uv pip install -e .`

3. edit cmsend.py and test, finally commit your changes

[chatmail/workflows](https://github.com/chatmail/workflows)
defines py-checks for this repository.
Run checks locally with `uvx ruff check .` and `uvx ruff format --check .`

To release, update CHANGELOG.md, then create and push a version tag:

    git tag -a v0.5.0 -m "Release v0.5.0"
    git push origin main v0.5.0

The release.yml workflow then builds and publishes to PyPI via
trusted publishing (OIDC); no local twine or PyPI token is involved.
