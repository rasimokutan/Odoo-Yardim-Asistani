"""
Standalone documentation indexer for Odoo Help Assistant.

Runs OUTSIDE of an Odoo process. Useful when:
  - Odoo is already running and you don't want to upgrade just to reindex.
  - The web wizard times out during a long indexing run.
  - You want progress visible in a terminal.

Strategy:
  1. Mirror the official odoo/documentation repo locally via `git clone`
     / `git pull` (depth=1, single branch). This avoids GitHub's 60/hour
     anonymous REST rate limit that silently breaks the listing-based
     indexer.
  2. Walk the local checkout, extract & chunk RST, embed via Ollama,
     INSERT into `odoo_rag_chunk` over psycopg2.

Usage (PowerShell, while Odoo is running):
  venv\\Scripts\\python.exe custom_addons\\odoo_help_assistant\\scripts\\index_docs_cli.py \\
      --db odoo19_v1 --branch 19.0 --max-files 80

Environment overrides:
  OLLAMA_URL        default http://127.0.0.1:11434
  EMBED_MODEL       default nomic-embed-text
  PGHOST/PGPORT/PGUSER/PGPASSWORD  default localhost/5432/odoo/odoo
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import psycopg2
import requests

DOC_REPO_URL = "https://github.com/odoo/documentation.git"
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("index_docs")


def default_cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "odoo_help_assistant_cache"


def clean_rst(text: str) -> str:
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


def chunk_text(text: str, title: str, section: str):
    words = text.split()
    out = []
    start = 0
    idx = 0
    while start < len(words):
        end = min(start + CHUNK_WORDS, len(words))
        body = " ".join(words[start:end])
        if len(body.strip()) > 60:
            out.append({
                "title": title, "content": body, "index": idx, "section": section,
            })
            idx += 1
        start = end - CHUNK_OVERLAP
        if end == len(words):
            break
    return out


def run_git(args, cwd=None):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=600)


def ensure_repo(cache_dir: Path, branch: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = cache_dir / f"odoo_documentation_{branch}"
    if (repo_dir / ".git").is_dir():
        log.info("Updating existing clone (%s)...", branch)
        r = run_git(["fetch", "--depth=1", "origin", branch], cwd=str(repo_dir))
        if r.returncode != 0:
            log.warning("git fetch warning: %s", (r.stdout + r.stderr).strip()[:200])
        r = run_git(["reset", "--hard", f"origin/{branch}"], cwd=str(repo_dir))
        if r.returncode != 0:
            raise SystemExit(f"git reset failed: {(r.stdout + r.stderr).strip()[:300]}")
    else:
        log.info("Cloning Odoo documentation (~50 MB)...")
        r = run_git(["clone", "--depth=1", "--branch", branch, DOC_REPO_URL, str(repo_dir)])
        if r.returncode != 0:
            raise SystemExit(f"git clone failed: {(r.stdout + r.stderr).strip()[:300]}")
    return repo_dir


def collect_rst(repo_dir: Path, subdirs, max_files: int, per_section: int | None = None):
    """
    Collect RST files, distributed across sections.

    If per_section is set, takes up to that many files from each section.
    Otherwise distributes max_files evenly across available sections so
    one large section (e.g. inventory_and_mrp) does not crowd everything
    else out.
    """
    apps_root = repo_dir / "content" / "applications"
    buckets: list[tuple[str, list[Path]]] = []
    for sub in subdirs:
        d = apps_root / sub
        if not d.is_dir():
            continue
        buckets.append((sub, sorted(d.rglob("*.rst"))))
    if not buckets:
        return [], apps_root

    if per_section is None and max_files > 0:
        per_section = max(1, max_files // len(buckets))

    out: list[Path] = []
    for sub, files in buckets:
        out.extend(files[:per_section])
    if max_files > 0 and len(out) > max_files:
        # Trim while keeping section diversity: round-robin instead of slice.
        rr = []
        idx = 0
        remaining = list(out)
        # rebuild as interleaved
        per_bucket = {sub: files[:per_section] for sub, files in buckets}
        keys = list(per_bucket.keys())
        while remaining and len(rr) < max_files:
            k = keys[idx % len(keys)]
            if per_bucket[k]:
                p = per_bucket[k].pop(0)
                rr.append(p)
                if p in remaining:
                    remaining.remove(p)
            idx += 1
            if all(not v for v in per_bucket.values()):
                break
        out = rr
    return out, apps_root


def embed(ollama_url, model, text, timeout=60):
    r = requests.post(
        f"{ollama_url}/api/embed",
        json={"model": model, "input": text},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    vecs = data.get("embeddings") or data.get("embedding")
    if not vecs:
        raise RuntimeError("empty embedding response")
    return vecs[0] if isinstance(vecs[0], list) else vecs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("PGDATABASE", "odoo19_v1"))
    ap.add_argument("--branch", default="19.0")
    ap.add_argument("--max-files", type=int, default=80)
    ap.add_argument("--ollama", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    ap.add_argument("--model", default=os.environ.get("EMBED_MODEL", "nomic-embed-text"))
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--no-clear", action="store_true", help="Append instead of wiping table")
    ap.add_argument("--dirs", nargs="*", help="Override DOC_DIRS subdirectories")
    ap.add_argument("--per-section", type=int, default=None,
                    help="Per-section file cap (default: max_files / sections)")
    args = ap.parse_args()

    cache_dir = Path(args.cache_dir) if args.cache_dir else default_cache_dir()
    dirs = args.dirs or DOC_DIRS

    repo_dir = ensure_repo(cache_dir, args.branch)
    files, apps_root = collect_rst(repo_dir, dirs, args.max_files, args.per_section)
    if not files:
        log.error("No RST files found under %s", apps_root)
        sys.exit(1)
    log.info("Will process %d RST files", len(files))

    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ.get("PGUSER", "odoo"),
        password=os.environ.get("PGPASSWORD", "odoo"),
        dbname=args.db,
    )
    conn.autocommit = False
    cur = conn.cursor()

    if not args.no_clear:
        cur.execute("DELETE FROM odoo_rag_chunk")
        log.info("Cleared %d existing chunks", cur.rowcount)
        conn.commit()

    indexed = skipped = errors = 0
    for i, path in enumerate(files, 1):
        rel = path.relative_to(apps_root)
        section = rel.parts[0] if len(rel.parts) > 1 else ""
        title = path.stem.replace("_", " ").title()
        log.info("[%d/%d] %s / %s", i, len(files), section or "-", title)
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log.warning("read fail %s: %s", path, exc)
            skipped += 1
            continue
        cleaned = clean_rst(raw)
        if len(cleaned.split()) < 30:
            skipped += 1
            continue
        chunks = chunk_text(cleaned, title, section)
        src = (
            f"https://github.com/odoo/documentation/blob/"
            f"{args.branch}/content/applications/{rel.as_posix()}"
        )
        for ch in chunks:
            try:
                vec = embed(args.ollama, args.model, ch["content"])
                cur.execute(
                    """
                    INSERT INTO odoo_rag_chunk
                      (title, section, source_url, content, embedding_json, chunk_index,
                       create_uid, create_date, write_uid, write_date)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, NOW(), 1, NOW())
                    """,
                    (ch["title"], ch["section"], src, ch["content"],
                     json.dumps(vec), ch["index"]),
                )
                indexed += 1
            except Exception as exc:
                log.warning("embed/insert fail (%s chunk %s): %s", title, ch["index"], exc)
                errors += 1
        conn.commit()
        time.sleep(0.02)

    cur.execute("SELECT COUNT(*) FROM odoo_rag_chunk")
    total = cur.fetchone()[0]
    log.info("DONE files=%d indexed=%d skipped=%d errors=%d total_in_db=%d",
             len(files), indexed, skipped, errors, total)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
