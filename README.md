<h1> mypygls </h1>

<p align="center">
  <a href="https://github.com/gjeusel/mypygls/actions?query=workflow%3ACI+branch%3Amain">
      <img src="https://github.com/gjeusel/mypygls/workflows//CI/badge.svg?event=push&branch=main" alt="Test Suite" onerror="this.style.display='none'">
  </a>
  <a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/gjeusel/mypygls" alt="Test Coverage" onerror="this.style.display='none'">
      <img src="https://coverage-badge.samuelcolvin.workers.dev/gjeusel/mypygls.svg" alt="Coverage">
  </a>
  <a href="https://pypi.org/project/mypygls/">
      <img src="https://badge.fury.io/py/mypygls.svg" alt="Package version" onerror="this.style.display='none'">
  </a>
  <a href="https://gjeusel.github.io/mypygls/">
    <img src="https://img.shields.io/badge/mkdocs-pages-brightgreen" alt="MKDocs github page">
  </a>
  <a href="https://github.com/pre-commit/pre-commit">
      <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white" alt="pre-commit">
  </a>
</p>

<p align="center">
  <em>Mypy turned into LSP.</em>
</p>

---

## Installation

```bash
pip install mypygls
```

### Developper

##### Install

```bash
make install
```

##### Launch tests:

```bash
pytest
```

##### Write docs:

```bash
mkdocs serve --watch .
```

### Update Cookiecutter Template

```bash
cruft update --skip-apply-ask --allow-untracked-files --project-dir .
```
