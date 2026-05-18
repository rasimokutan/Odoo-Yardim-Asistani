"""
Odoo documentation indexer.

Strategy:
  1. Mirror the official odoo/documentation repo locally via `git clone`
     / `git pull` (shallow clone, branch-specific). No GitHub REST API
     calls are used, so we are not subject to the 60/hour anonymous
     rate limit that made the old listing-based indexer silently
     return 0/0/0.
  2. Walk the local checkout, read .rst files under selected app
     directories, clean RST markup to plain text, split into ~350-word
     overlapping chunks.
  3. Embed each chunk via Ollama (`nomic-embed-text`) and store it in
     `odoo.rag.chunk`.
"""

import logging
import os
import re
import subprocess
import time
from pathlib import Path

from .embedding_service import EmbeddingService
from .exceptions import ChatbotServiceError

_logger = logging.getLogger(__name__)

DOC_REPO_URL = "https://github.com/odoo/documentation.git"
# Subdirectories of `content/applications/` to index. Matches the Odoo 19
# documentation tree.
DOC_DIRS = [
    "inventory_and_mrp",
    "sales",
    "finance",
    "hr",
    "services",
    "general",
    "websites",
    "productivity",
    "essentials",
    "marketing",
    "studio",
]
CHUNK_WORDS = 350
CHUNK_OVERLAP = 50


# ── Local cache directory ─────────────────────────────────────────────────────

def _default_cache_dir() -> Path:
    """Where to keep the cloned Odoo documentation repo."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "odoo_help_assistant_cache"


# ── RST cleaner ───────────────────────────────────────────────────────────────

def _clean_rst(text: str) -> str:
    """Strip RST markup and return readable plain text."""
    text = re.sub(r"\.\. code-block::.*?\n\n.*?\n\n", " ", text, flags=re.DOTALL)
    text = re.sub(r"::\n\n\s{3,}.*?\n\n", " ", text, flags=re.DOTALL)
    text = re.sub(r"\.\. \w+::.*?\n", "", text)
    text = re.sub(r"^\s+:\w[\w-]*:.*$", "", text, flags=re.MULTILINE)
    text = re.sub(
        r":(?:ref|doc|class|meth|attr|func|mod|data|obj|abbr|guilabel|menuselection|kbd|dfn):`[^`]*`",
        "",
        text,
    )
    text = re.sub(r"``([^`]*)``", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]*)\*", r"\1", text)
    text = re.sub(r"`([^`]*)`_?", r"\1", text)
    text = re.sub(r"^[=\-~^#*+]{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\.\. toctree::.*?\n\n.*?\n\n", "", text, flags=re.DOTALL)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ── Chunker ───────────────────────────────────────────────────────────────────

def _chunk_text(text: str, title: str, section: str | None = None) -> list[dict]:
    words = text.split()
    chunks = []
    start = 0
    idx = 0
    while start < len(words):
        end = min(start + CHUNK_WORDS, len(words))
        chunk_text = " ".join(words[start:end])
        if len(chunk_text.strip()) > 60:
            chunks.append({
                "title": title,
                "content": chunk_text,
                "index": idx,
                "section": section,
            })
            idx += 1
        start = end - CHUNK_OVERLAP
        if end == len(words):
            break
    return chunks


# ── Git mirror ────────────────────────────────────────────────────────────────

def _run_git(args: list[str], cwd: Path | None = None, timeout: int = 600) -> tuple[int, str]:
    cmd = ["git"] + args
    try:
        res = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
        return res.returncode, (res.stdout + res.stderr).strip()
    except FileNotFoundError as exc:
        raise ChatbotServiceError(
            "`git` komutu bulunamadı. Lütfen Git for Windows kurun ve PATH'e ekleyin."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ChatbotServiceError(f"git komutu zaman aşımına uğradı: {' '.join(args)}") from exc


def _ensure_repo(cache_dir: Path, branch: str, log) -> Path:
    """Clone or fast-forward the documentation repo for `branch`."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = cache_dir / f"odoo_documentation_{branch}"

    if (repo_dir / ".git").is_dir():
        log(f"Mevcut dokümantasyon klonu güncelleniyor ({branch})...")
        rc, out = _run_git(["fetch", "--depth=1", "origin", branch], cwd=repo_dir)
        if rc != 0:
            log(f"git fetch uyarısı: {out[:200]}")
        rc, out = _run_git(["reset", "--hard", f"origin/{branch}"], cwd=repo_dir)
        if rc != 0:
            raise ChatbotServiceError(f"git reset başarısız: {out[:200]}")
    else:
        log(f"Odoo dokümantasyonu klonlanıyor (~50 MB, ilk seferde 1-2 dk)...")
        rc, out = _run_git(
            ["clone", "--depth=1", "--branch", branch, DOC_REPO_URL, str(repo_dir)],
            cwd=cache_dir,
        )
        if rc != 0:
            raise ChatbotServiceError(f"git clone başarısız: {out[:300]}")
    return repo_dir


def _collect_rst_files(repo_dir: Path, subdirs: list[str], max_files: int) -> list[Path]:
    """
    Collect RST files, interleaved across sections so a single large
    section does not consume the whole budget.
    """
    apps_root = repo_dir / "content" / "applications"
    buckets: list[tuple[str, list[Path]]] = []
    for sub in subdirs:
        d = apps_root / sub
        if d.is_dir():
            buckets.append((sub, sorted(d.rglob("*.rst"))))
    if not buckets:
        return []

    per_section = max(1, max_files // len(buckets)) if max_files else 0
    per_bucket = {sub: list(files[:per_section] if per_section else files)
                  for sub, files in buckets}

    rr: list[Path] = []
    keys = list(per_bucket.keys())
    idx = 0
    while keys and (max_files == 0 or len(rr) < max_files):
        k = keys[idx % len(keys)]
        if per_bucket[k]:
            rr.append(per_bucket[k].pop(0))
        idx += 1
        if all(not v for v in per_bucket.values()):
            break
    return rr


# ── Main indexer ──────────────────────────────────────────────────────────────

class DocIndexer:
    def __init__(
        self,
        env,
        base_url: str,
        branch: str = "19.0",
        token: str | None = None,  # kept for API compatibility, unused
        max_files: int = 80,
        cache_dir: str | None = None,
        subdirs: list[str] | None = None,
    ):
        self.env = env
        self.branch = branch
        self.max_files = max_files
        self.embedder = EmbeddingService(base_url)
        self.cache_dir = Path(cache_dir) if cache_dir else _default_cache_dir()
        self.subdirs = subdirs or DOC_DIRS

    def run(self, progress_callback=None) -> dict:
        """
        Mirror docs locally, embed chunks, write to DB.

        Returns {"indexed": N, "skipped": M, "errors": K, "files": F}.
        """
        def _log(msg):
            _logger.info(msg)
            if progress_callback:
                progress_callback(msg)

        repo_dir = _ensure_repo(self.cache_dir, self.branch, _log)

        files = _collect_rst_files(repo_dir, self.subdirs, self.max_files)
        if not files:
            raise ChatbotServiceError(
                f"İndekslenecek RST dosyası bulunamadı. "
                f"Klon dizini: {repo_dir}"
            )
        _log(f"{len(files)} RST dosyası bulundu. Mevcut chunk'lar siliniyor...")
        self.env["odoo.rag.chunk"].sudo().search([]).unlink()
        self.env.cr.commit()

        indexed = skipped = errors = 0
        apps_root = repo_dir / "content" / "applications"

        import json as _json

        for i, path in enumerate(files, 1):
            try:
                rel = path.relative_to(apps_root)
            except ValueError:
                rel = path
            section = rel.parts[0] if len(rel.parts) > 1 else None
            title = path.stem.replace("_", " ").title()
            _log(f"[{i}/{len(files)}] {section or '-'} / {title}")

            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                _logger.warning("read fail %s: %s", path, exc)
                skipped += 1
                continue

            cleaned = _clean_rst(raw)
            if len(cleaned.split()) < 30:
                skipped += 1
                continue

            chunks = _chunk_text(cleaned, title, section)
            source_url = (
                f"https://github.com/odoo/documentation/blob/"
                f"{self.branch}/content/applications/{rel.as_posix()}"
            )

            for chunk_data in chunks:
                try:
                    vector = self.embedder.embed(chunk_data["content"])
                    self.env["odoo.rag.chunk"].sudo().create({
                        "title": chunk_data["title"],
                        "section": chunk_data.get("section") or "",
                        "source_url": source_url,
                        "content": chunk_data["content"],
                        "embedding_json": _json.dumps(vector),
                        "chunk_index": chunk_data["index"],
                    })
                    indexed += 1
                except ChatbotServiceError as exc:
                    _logger.warning("Embedding failed for chunk: %s", exc)
                    errors += 1
                except Exception:
                    _logger.exception("Unexpected chunk error")
                    errors += 1

            # Commit per-file so progress is visible if the long-running
            # request is cut off by a frontend timeout.
            self.env.cr.commit()
            time.sleep(0.02)

        summary = {
            "indexed": indexed,
            "skipped": skipped,
            "errors": errors,
            "files": len(files),
        }
        _log(f"Tamamlandı: {summary}")
        return summary
