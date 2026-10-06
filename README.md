# cmsend: chatmail sendmail tool for end-to-end encrypted messages

**WORK IN PROGRESS: this is more an explorative study for now**

To install use:

    uv tool install cmsend

To send and receive from a single chatmail relay:

    cmsend --init nine.testrun.org   # <-- substitute with the domain you want to set as origin

The profile's display name is `cmsend[HOSTNAME]`,
so recipients see which host a message came from.

To setup a tagged chat using an invite link:

    cmsend -t LOG --join "INVITELINK"       # <-- quotes are necessary because links contain "&"

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

To release, run the shared release script from a checkout of
[chatmail/workflows](https://github.com/chatmail/workflows):

    python ../workflows/scripts/make_new_release.py

It runs the checks, tests the built wheel, generates the CHANGELOG.md
entry with git-cliff and opens it in your editor, then commits, tags
vX.Y.Z and pushes. The release.yml workflow builds and publishes to
PyPI via trusted publishing (OIDC); no local twine or PyPI token is
involved.
