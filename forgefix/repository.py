"""Read data without importing it; copy only a bounded, plain-file snapshot."""
import ast
import hashlib
import re
import shutil
import stat
from pathlib import Path

MAX_FILE = 64_000
MAX_FILES = 200
MAX_TOTAL = 2_000_000
IGNORED = {".git", ".venv", "node_modules", "__pycache__", ".env", ".codex"}


class PolicyError(ValueError):
    pass


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plain_files(root: Path) -> list[Path]:
    """Reject symlinks and devices, including ignored names. No link traversal."""
    result: list[Path] = []
    total, entries = 0, 0

    def visit(directory: Path) -> None:
        nonlocal total, entries
        for entry in directory.iterdir():
            entries += 1
            if entries > 1000:
                raise PolicyError("Repository exceeds directory-entry limit")
            mode = entry.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise PolicyError(f"Non-regular repository entry: {entry.name}")
            if entry.name in IGNORED or entry.name.startswith("."):
                continue
            if entry.is_dir():
                # Bound traversal even for trees containing only directories.
                if len(entry.relative_to(root).parts) > 12:
                    raise PolicyError("Repository directory depth exceeds 12")
                visit(entry)
            else:
                size = entry.stat().st_size
                total += size
                if size > MAX_FILE or total > MAX_TOTAL or len(result) >= MAX_FILES:
                    raise PolicyError("Repository exceeds snapshot limits")
                result.append(entry)

    visit(root)
    return sorted(result)


def snapshot(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise PolicyError("Repository must be a regular directory")
    files = plain_files(source)
    destination.mkdir(parents=True, exist_ok=False)
    for path in files:
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        target.chmod(0o644)


def code_map(root: Path) -> list[dict]:
    result = []
    for path in plain_files(root):
        # Tests and docs are not code-executed. Hidden evaluator tests live elsewhere.
        if path.suffix != ".py" or path.relative_to(root).parts[0] != "src":
            continue
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
            symbols = [{"name": n.name, "line": n.lineno, "kind": type(n).__name__}
                       for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            imports = [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        except (SyntaxError, RecursionError):
            symbols, imports = [], []
        result.append({"path": path.relative_to(root).as_posix(), "sha256": digest(text),
                       "lines": len(text.splitlines()), "symbols": symbols, "imports": imports})
    return result


def search(root: Path, issue: str, mapping: list[dict], limit: int = 6) -> list[dict]:
    terms = set(re.findall(r"[a-z_]{3,}", issue.lower()))
    ranked = []
    for item in mapping:
        content = (root / item["path"]).read_text(encoding="utf-8")
        haystack = (item["path"] + " " + content).lower()
        score = sum(haystack.count(term) for term in terms)
        ranked.append((score, item["path"], {**item, "content": content}))
    return [item for _, _, item in sorted(ranked, key=lambda x: (-x[0], x[1]))[:limit]]

