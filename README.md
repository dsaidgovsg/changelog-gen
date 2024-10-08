# `cc-changelog-gen`

[Conventional Commit](https://www.conventionalcommits.org/en/v1.0.0/) Changelog Generator for git
repositories.

## Developer Set-up

This set-up assumes you have a fresh Python environment with Python 3.11 and above.

Since Python 3.11 might be fairly new, you are recommended to spin up a new Python environment with
`pyenv`:

```bash
pyenv install 3.11
pyenv virtualenv 3.11 cc-changelog-gen-3.11
pyenv activate cc-changelog-gen-3.11
```

With the Python environment set up, run the following to get `pip-tools` and upgrade other relevant
tools:

```bash
pip install pip setuptools wheel pip-tools --upgrade
```

You should immediately restart the terminal session to ensure `pip-compile` is made available.

With the new terminal session, if you are only interested to run the program:

```bash
pip-compile -o requirements.txt
pip install -r requirements.txt
```

If you are a dev and wants to update the repository, you will need the extra dev tools:

```bash
pip-compile -o requirements.dev.txt --extra dev
pip install -r requirements.dev.txt
```

At the end of updating the repository code, you should run:

```bash
black .
```

to auto-format the entire code base.

## `.clog.yaml` Configuration

The parsing of the commit messages (in particular the titles) can be controlled via the values set
by `.clog.yaml` in the current working directory

If you prefer to have a different file name or path to it, you can override this value, e.g.

```bash
cc-changelog-gen ... -c /path/to/.clog.yaml`
```

For the YAML specifications, as the parsing feature set is still growing and fairly unstable, there
will not be any specifications yet and do expect new / breaking changes to take place (though any
major changes will be tagged.)

Refer to the example [`.clog.yaml`](.clog.yaml) for usage at the moment.

## CLI Install

If you prefer to install the CLI within its own Python environment, you might want to follow the
`pyenv` set-up in the earlier [Developer Set-up](#developer-set-up), before coming back to this
section.

Once you are in your preferred environment, you will need to install the package first. To do so
locally (if you git-cloned the repository):

```bash
pip install -e .
```

You should restart the terminal session to ensure `cc-changelog-gen` is within `PATH`.

Now you can run the following:

```bash
# Simple example pointing to current directory for repo
cc-changelog-gen -t v1.0.0 HEAD

# Complex example pointing to another directory and between commits
cc-changelog-gen -t v1.0.0 -r ./path/to/repo aaaabbb^..ccccddd
```

### Special Commits Range Syntax

Since it is very common to want to generate changelogs between a previous semver tag version to
current `HEAD`, a special syntax `~..` was provided to allow finding the latest previous semver tag
in the specified repository, depending on the given title value (`-t`, `--title` flag).

#### Scenario 1a

Given the repository has tags (`v` or `V` prefix is acceptable):

```python
["1.0.0", "1.1.0", "1.1.5", "1.2.0", "v2.0.0", "invalid-semver-tags-are-ignored"]
```

and the given `-t` value is `1.1.7`:

```bash
cc-changelog-gen -t 1.1.7 ~..HEAD
```

The closest previous semver tag is `1.1.5`, so the above is equivalent to:

```bash
cc-changelog-gen -t 1.1.7 1.1.5..HEAD
```

#### Scenario 1b

Continuing from Scenario 1a, if no `-t` value is given:

```bash
cc-changelog-gen ~..HEAD
```

It will simply use the latest semver tag, which is `v2.0.0` so the above is equivalent to:

```bash
cc-changelog-gen v2.0.0..HEAD
```

#### Scenario 2

If the repository has no valid semver tags, it doesn't matter if `-t` value is given or not.

So given:

```bash
cc-changelog-gen ~..HEAD
```

The `~..` is simply dropped, to start from the beginning of all commits, equivalent to:

```bash
cc-changelog-gen HEAD
```

## Docker Build and Usage

To build the image from scratch:

```bash
IMAGE_TAG="latest"
docker build . -t "dsaidgovsg/cc-changelog-gen:${IMAGE_TAG}"
```

The entrypoint of the image is set to `cc-changelog-gen`, so to run with the CLI within the image:

```bash
docker run --rm -it -v /host/git/repo:/app/repo:ro -v /host/.clog.yaml:/app/.clog.yaml:ro "dsaidgovsg/cc-changelog-gen:${IMAGE_TAG}" \
    -t "SOME_TITLE" -r /app/repo ~..HEAD
```

### Docker Image Caveat

`git`'s' `safe.directory` configuration by default to allow all directories from any users. This is
because the most likely use case is to mount the host git repo into the running container, and this
mounted directory is very likely to have a different user from the `clog` non-root user in the
image.

This setting can be found in `/app/.gitconfig` and amendable as `clog` non-root image user.

For more details on `safe.directory`:
<https://git-scm.com/docs/git-config/2.35.2#Documentation/git-config.txt-safedirectory>
