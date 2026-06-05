"""Stage 0 acceptance test — scaffold structure and core imports."""
import importlib
import os


def test_core_imports():
    """Core stack packages must be importable."""
    for pkg in ["fastapi", "sqlalchemy", "jinja2", "pydantic"]:
        mod = importlib.import_module(pkg)
        assert mod is not None, f"{pkg} not importable"


def test_app_directories():
    """All expected app directories must exist."""
    root = os.path.dirname(os.path.dirname(__file__))
    required = [
        "app",
        "app/models",
        "app/schemas",
        "app/api",
        "app/services",
        "app/services/evidence",
        "app/services/methodology",
        "app/services/qa",
        "app/services/deliverables",
        "app/services/ptorc",
        "app/packs/dpdp",
        "app/packs/vapt",
        "app/frameworks",
        "app/web/templates",
        "app/web/static",
        "app/bot",
        "migrations",
        "ptorc-adapter",
        "tests",
    ]
    for d in required:
        assert os.path.isdir(os.path.join(root, d)), f"Missing directory: {d}"


def test_evidence_files_present():
    """Evidence tracker source files must be in place."""
    root = os.path.dirname(os.path.dirname(__file__))
    required = [
        "app/services/evidence/extract.py",
        "app/services/evidence/classify.py",
        "app/services/evidence/utils.py",
        "app/services/evidence/manifest.py",
    ]
    for f in required:
        assert os.path.isfile(os.path.join(root, f)), f"Missing file: {f}"


def test_config_files_present():
    """Root config files must exist."""
    root = os.path.dirname(os.path.dirname(__file__))
    required = [
        "pyproject.toml",
        "CLAUDE.md",
        ".env.example",
        ".gitignore",
        "alembic.ini",
        "README.md",
    ]
    for f in required:
        assert os.path.isfile(os.path.join(root, f)), f"Missing config file: {f}"


def test_pack_placeholders():
    """Pack JSON files must exist."""
    root = os.path.dirname(os.path.dirname(__file__))
    for f in ["app/packs/dpdp/pack.json", "app/packs/vapt/pack.json"]:
        assert os.path.isfile(os.path.join(root, f)), f"Missing pack: {f}"
