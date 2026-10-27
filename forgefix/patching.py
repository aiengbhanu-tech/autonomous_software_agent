import ast
import difflib
from pathlib import Path, PurePosixPath

from .repository import MAX_FILE, PolicyError, digest
from .types import Edit


def apply_edits(root: Path, edits: list[Edit]) -> str:
    """Validate the entire proposal before writing any source file."""
    if not 1 <= len(edits) <= 3:
        raise PolicyError("One to three source edits required")
    changes, seen = [], set()
    for edit in edits:
        path = PurePosixPath(edit.path)
        if (not edit.path or "\\" in edit.path or path.is_absolute() or ".." in path.parts
                or path.parts[0] != "src" or path.suffix != ".py"
                or any(p.startswith(".") for p in path.parts) or path.as_posix() in seen):
            raise PolicyError("Only unique existing src/**/*.py files may be edited")
        seen.add(path.as_posix())
        target = root.joinpath(*path.parts)
        if any(p.is_symlink() for p in [target, *target.parents] if p != root.parent):
            raise PolicyError("Symlink patch target denied")
        if not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
            raise PolicyError("Patch target must exist inside snapshot")
        before = target.read_text(encoding="utf-8")
        if digest(before) != edit.before_sha256:
            raise PolicyError("Stale preimage hash")
        if len(edit.content.encode("utf-8")) > MAX_FILE:
            raise PolicyError("Patch exceeds byte limit")
        try:
            ast.parse(edit.content)
        except (SyntaxError, ValueError, RecursionError) as exc:
            raise PolicyError("Patch is not valid Python") from exc
        changes.append((target, before, edit.content, edit.path))
    diff = ""
    for target, before, after, path in changes:
        target.write_text(after, encoding="utf-8")
        diff += "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                          fromfile=f"a/{path}", tofile=f"b/{path}"))
    if not diff:
        raise PolicyError("Patch made no changes")
    return diff

