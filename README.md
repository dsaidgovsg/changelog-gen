# `cc-changelog-gen`

[Conventional Commit](https://www.conventionalcommits.org/en/v1.0.0/) Changelog Generator for git
repositories.

## Developer Set-up

This set-up assumes you have a fresh Python environment, e.g. `pyenv virtualenv cc-changelog-gen &&
pyenv activate cc-changelog-gen` with Python 3.10 and above.

First run the following to get `pip-tools` and upgrade other relevant tools:

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

## CLI Example

You will need to install the package first. To do so locally (if you git-cloned the repository):

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
