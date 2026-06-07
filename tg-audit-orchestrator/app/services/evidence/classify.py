#!/usr/bin/env python3
"""
AI-powered subject categorizer for audit documents.

Reads all converted .txt files from the converted_files folder,
uses Anthropic Claude to map each item to applicable audit subjects, then creates a
"categorized" sub-folder containing one merged .txt per subject.
"""

import json
import hashlib
import logging
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from app.services.evidence.utils import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BASE_DELAY_S,
    MAX_RETRY_DELAY_S,
    configure_utf8_output,
    load_env_file,
)

logger = logging.getLogger(__name__)


CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
# Use claude-haiku for subject discovery/classification — fast and cost-effective.
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
CATEGORIZATION_STATE_FILE = "_categorization_state.json"
CATEGORIZATION_TAXONOMY_VERSION = 5
DISCOVERY_PROMPT_CHAR_LIMIT = 12000
DISCOVERY_SNIPPET_CHARS = 600

# The catalog provides consistent names for common audit domains across
# assessment types. Additional domains can be discovered for specialized audits.
AUDIT_DOMAIN_CATALOG = {
    "Governance and General Controls": [
        "Governance and Compliance",
        "Risk Management",
        "Internal Audit and Assurance",
        "Third-Party Risk Management",
        "Business Continuity and Resilience",
        "Physical and Environmental Security",
    ],
    "Cybersecurity and IT Controls": [
        "Security Governance and ISMS",
        "Identity and Access Management",
        "Personnel Security",
        "Security Awareness and Training",
        "Asset Management",
        "Data Protection and Encryption",
        "Endpoint and Mobile Security",
        "Network and Perimeter Security",
        "Vulnerability and Patch Management",
        "Configuration and Change Management",
        "Logging and Security Monitoring",
        "Incident Response",
        "Backup and Recovery",
        "Application Security and SDLC",
        "Cloud and SaaS Security",
    ],
    "Privacy and Data Protection": [
        "Privacy Governance",
        "Data Lifecycle and Retention",
        "Data Subject Rights",
        "Cross-Border Data Transfers",
        "Privacy Incident Management",
    ],
    "AI Governance and Assurance": [
        "AI Governance and Accountability",
        "AI Risk and Impact Assessment",
        "AI Data Governance",
        "AI Model Development and Validation",
        "AI Transparency and Explainability",
        "AI Human Oversight and Use Controls",
        "AI Monitoring and Incident Management",
        "AI Security and Resilience",
        "AI Third-Party Management",
    ],
}


def read_text(path: Path) -> str:
    for enc in ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _corpus_signature(all_txt_files: Dict[str, Path]) -> str:
    """Return a stable signature for the current converted corpus."""
    digest = hashlib.sha256()
    for rel_key, path in sorted(all_txt_files.items()):
        digest.update(rel_key.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _file_signatures(all_txt_files: Dict[str, Path]) -> Dict[str, str]:
    return {rel_key: _file_sha256(path) for rel_key, path in all_txt_files.items()}


def _load_categorization_state(state_file: Path) -> Optional[Dict[str, object]]:
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read categorization state from %s: %s", state_file, exc)
        return None


def _restore_written_paths(categorized_dir: Path, state: Dict[str, object]) -> Dict[str, Path]:
    written_files = state.get("written_files")
    if not isinstance(written_files, dict):
        return {}

    restored: Dict[str, Path] = {}
    for subject, filename in written_files.items():
        if not isinstance(subject, str) or not isinstance(filename, str):
            return {}
        path = categorized_dir / filename
        if not path.exists():
            return {}
        restored[subject] = path
    return restored


def _save_categorization_state(
    state_file: Path,
    corpus_signature: str,
    subjects: List[str],
    file_signatures: Dict[str, str],
    file_map: Dict[str, List[str]],
    written: Dict[str, Path],
) -> None:
    state_payload = {
        "version": 1,
        "taxonomy_version": CATEGORIZATION_TAXONOMY_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "corpus_signature": corpus_signature,
        "subjects": subjects,
        "file_signatures": file_signatures,
        "file_map": file_map,
        "written_files": {subject: path.name for subject, path in written.items()},
    }
    state_file.write_text(json.dumps(state_payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _uses_current_taxonomy(state: Dict[str, object]) -> bool:
    return state.get("taxonomy_version") == CATEGORIZATION_TAXONOMY_VERSION


def _snippet(text: str, max_chars: int = 800) -> str:
    """Return a short representative snippet of a document."""
    return text[:max_chars].replace("\n", " ").strip()


def _catalog_domains() -> List[str]:
    return [
        subject
        for group_subjects in AUDIT_DOMAIN_CATALOG.values()
        for subject in group_subjects
    ]


def _normalize_audit_subject_name(subject: str) -> str:
    cleaned = " ".join(subject.split()).strip(" .-_")
    cleaned = re.sub(r"\b(?:Policy|Policies)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split()).strip(" .-_")
    return cleaned


def _normalize_audit_subjects(subjects: List[str], reserved: Optional[List[str]] = None) -> List[str]:
    reserved_lower = {subject.lower() for subject in (reserved or [])}
    normalized: List[str] = []
    for subject in subjects:
        canonical = _normalize_audit_subject_name(subject)
        if (
            canonical
            and canonical.lower() not in reserved_lower
            and canonical.lower() not in {item.lower() for item in normalized}
        ):
            normalized.append(canonical)
    return normalized


def _balanced_discovery_excerpt_block(snippets: Dict[str, str]) -> str:
    grouped: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for filename, snippet in sorted(snippets.items()):
        parts = Path(filename).parts
        group = parts[0] if len(parts) > 1 else "(root)"
        grouped[group].append((filename, snippet[:DISCOVERY_SNIPPET_CHARS]))

    selected: List[str] = []
    round_index = 0
    while True:
        added = False
        for group in sorted(grouped):
            entries = grouped[group]
            if round_index >= len(entries):
                continue
            filename, snippet = entries[round_index]
            candidate = f"FILE: {filename}\n{snippet}"
            next_block = "\n\n".join(selected + [candidate])
            if len(next_block) > DISCOVERY_PROMPT_CHAR_LIMIT:
                return "\n\n".join(selected)
            selected.append(candidate)
            added = True
        if not added:
            break
        round_index += 1
    return "\n\n".join(selected)


def _get_claude_client():
    if not CLAUDE_API_KEY:
        raise RuntimeError("CLAUDE_API_KEY is not set. Add it to your .env file.")
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic is not installed. Run: pip install anthropic") from exc
    return anthropic.Anthropic(api_key=CLAUDE_API_KEY)


def _normalize_model_text(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.startswith("```")).strip()
    return raw


def _parse_subject_array(raw: str, allowed_subjects: Optional[List[str]] = None) -> List[str]:
    normalized = _normalize_model_text(raw)
    candidates = [normalized]

    match = re.search(r"\[[\s\S]*\]", normalized)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                values = [str(item).strip() for item in parsed if str(item).strip()]
                if allowed_subjects:
                    matched = []
                    lowered_map = {subject.lower(): subject for subject in allowed_subjects}
                    for value in values:
                        canonical = lowered_map.get(value.lower())
                        if canonical and canonical not in matched:
                            matched.append(canonical)
                    return matched
                return values
        except json.JSONDecodeError:
            repaired = candidate.replace("\\", "\\\\")
            try:
                parsed = json.loads(repaired)
                if isinstance(parsed, list):
                    values = [str(item).strip() for item in parsed if str(item).strip()]
                    if allowed_subjects:
                        matched = []
                        lowered_map = {subject.lower(): subject for subject in allowed_subjects}
                        for value in values:
                            canonical = lowered_map.get(value.lower())
                            if canonical and canonical not in matched:
                                matched.append(canonical)
                        return matched
                    return values
            except json.JSONDecodeError:
                pass

    if allowed_subjects:
        matched = []
        lowered_text = normalized.lower()
        for subject in allowed_subjects:
            if subject.lower() in lowered_text and subject not in matched:
                matched.append(subject)
        if matched:
            return matched

    line_values = []
    for line in normalized.splitlines():
        value = line.strip().lstrip("-*0123456789. ").strip("\"' ")
        if value:
            line_values.append(value)

    if allowed_subjects:
        lowered_map = {subject.lower(): subject for subject in allowed_subjects}
        matched = []
        for value in line_values:
            canonical = lowered_map.get(value.lower())
            if canonical and canonical not in matched:
                matched.append(canonical)
        return matched

    return line_values


def _claude_request(client, prompt: str) -> str:
    """Call Claude and return the response text with basic retry handling."""
    delay = DEFAULT_RETRY_BASE_DELAY_S
    last_err = None
    for attempt in range(DEFAULT_MAX_RETRIES):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as exc:
            last_err = exc
            err_str = str(exc)
            lowered = err_str.lower()
            is_transient = (
                "quota" in lowered
                or "429" in err_str
                or "503" in err_str
                or "overloaded" in lowered
                or "unavailable" in lowered
                or "timeout" in lowered
                or "timed out" in lowered
            )
            if is_transient and attempt < DEFAULT_MAX_RETRIES - 1:
                logger.warning(
                    "Transient Claude error, waiting %.0fs (attempt %s/%s): %s",
                    delay,
                    attempt + 1,
                    DEFAULT_MAX_RETRIES,
                    exc,
                )
                time.sleep(delay)
                delay = min(delay * 2, MAX_RETRY_DELAY_S)
            else:
                raise
    raise RuntimeError(f"Claude failed after {DEFAULT_MAX_RETRIES} attempts: {last_err}")


def _discover_subjects(client, snippets: Dict[str, str], progress: Callable) -> List[str]:
    catalog_domains = _catalog_domains()
    progress("AI: Checking whether evidence needs specialized audit domains beyond the standard catalog...")
    prompt = f"""You are an expert auditor working across cybersecurity, privacy, AI, operational,
compliance, financial, and other assessment types.

The standard audit-domain catalog below will already be available for classification:
{json.dumps(AUDIT_DOMAIN_CATALOG, indent=2)}

Review the representative evidence excerpts below and identify ONLY any additional audit
control domains needed because the evidence is materially outside the catalog. A new
domain is appropriate for a specialized audit topic (for example, revenue recognition,
environmental compliance, or occupational safety), not merely because a document has a
different title.

Rules:
- Return ONLY a JSON array of additional domain-name strings, or [] when the catalog is sufficient.
- Do not repeat, rename, or narrow a domain already covered by the catalog.
- Use professional audit-domain names that describe the control objective.
- Never use "Policy", "Policies", filenames, file types, or evidence artifact names as domains.
- Policies, screenshots, logs, registers, reports, tickets, and test results are evidence types,
  not audit subjects.

REPRESENTATIVE EVIDENCE EXCERPTS:
{_balanced_discovery_excerpt_block(snippets)}
"""
    raw = _claude_request(client, prompt)
    additional_domains = _normalize_audit_subjects(
        _parse_subject_array(raw),
        reserved=catalog_domains,
    )
    if additional_domains:
        progress(f"Added specialized audit subjects: {', '.join(additional_domains)}")
    else:
        progress("Standard audit-domain catalog covers the available evidence.")
    return catalog_domains + additional_domains


def _classify_files(
    client,
    snippets: Dict[str, str],
    subjects: List[str],
    progress: Callable,
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    subject_map: Dict[str, List[str]] = {subject: [] for subject in subjects}
    file_map: Dict[str, List[str]] = {}
    subjects_json = json.dumps(subjects)

    files = list(snippets.items())
    total = len(files)

    for idx, (filename, snip) in enumerate(files, 1):
        progress(f"AI: Classifying file {idx}/{total}: {filename}")

        prompt = f"""You are an expert IT/security auditor.
Classify the following evidence document into the audit control domain(s) it supports.

AVAILABLE SUBJECTS:
{subjects_json}

DOCUMENT FILENAME: {filename}
DOCUMENT EXCERPT:
{snip}

Rules:
- Respond with ONLY a JSON array of subject name strings chosen from the list above.
- Choose 1-3 subjects that best match. If unsure, pick the single closest one.
- Do not invent new subjects - use exact strings from the list.
- Treat a policy as governance evidence for its underlying control domain, not as the domain itself.
- Prioritize operational relevance: logs, configurations, exports, screenshots, tests, tickets,
  inventories, training records, and recovery results demonstrate operation of controls.
- Use the document content and evidentiary purpose, not merely its filename or folder.

Example response: ["Identity and Access Management"]
"""
        try:
            raw = _claude_request(client, prompt)
            chosen = _parse_subject_array(raw, allowed_subjects=subjects)
            if not chosen:
                raise ValueError("No valid subjects recovered from Claude response")
        except Exception as exc:
            logger.warning("Classification failed for %s: %s. Assigning to first subject.", filename, exc)
            chosen = [subjects[0]]

        assigned: List[str] = []
        for subject in chosen:
            subject = subject.strip()
            if subject in subject_map:
                subject_map[subject].append(filename)
                assigned.append(subject)
                continue
            matched = next((key for key in subject_map if key.lower() == subject.lower()), None)
            if matched:
                subject_map[matched].append(filename)
                assigned.append(matched)
            else:
                subject_map[subjects[0]].append(filename)
                assigned.append(subjects[0])

        file_map[filename] = assigned

    return subject_map, file_map


def _write_subject_files(
    categorized_dir: Path,
    subject_map: Dict[str, List[str]],
    converted_dir: Path,
    all_txt_files: Dict[str, Path],
    progress: Callable,
) -> Dict[str, Path]:
    """Write one .txt file per subject into categorized_dir."""
    categorized_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source_sep = "-" * 60

    for subject, filenames in subject_map.items():
        if not filenames:
            continue

        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in subject).strip().replace(" ", "_")
        out_path = categorized_dir / f"{safe_name}.txt"

        progress(f"Writing subject file: {out_path.name} ({len(filenames)} source files)")

        lines = [
            "=" * 80,
            f"SUBJECT: {subject}",
            "=" * 80,
            f"Generated: {now}",
            f"Source files ({len(filenames)}):",
        ]
        for filename in sorted(filenames):
            lines.append(f"  - {filename}")
        lines += ["=" * 80, ""]

        for filename in sorted(filenames):
            src_path = all_txt_files.get(filename)
            if src_path is None:
                lines += [f"\n{source_sep}", f"SOURCE: {filename}", source_sep, "[File not found in converted directory]", ""]
                continue
            content = read_text(src_path)
            display_path = src_path.relative_to(converted_dir) if src_path.is_relative_to(converted_dir) else src_path
            lines += [
                f"\n{source_sep}",
                f"SOURCE FILE: {filename}",
                f"PATH: {display_path}",
                source_sep,
                content,
                "",
            ]

        out_path.write_text("\n".join(lines), encoding="utf-8")
        written[subject] = out_path

    expected_names = {path.name for path in written.values()}
    for existing in categorized_dir.glob("*.txt"):
        if existing.name not in expected_names:
            existing.unlink(missing_ok=True)

    return written


def run_categorization(
    converted_dir: str,
    progress_callback: Optional[Callable] = None,
) -> Tuple[Dict[str, Path], Dict[str, List[str]]]:
    """
    Main entry point for subject categorization.

    Returns:
        written  : {subject_name: Path of generated subject .txt file}
        file_map : {converted_filename: [subject_name, ...]}
    """
    progress = progress_callback or (lambda msg: logger.info(msg))
    converted_path = Path(converted_dir)

    if not converted_path.exists():
        raise FileNotFoundError(f"Converted directory not found: {converted_dir}")

    categorized_dir = converted_path / "categorized"
    state_file = categorized_dir / CATEGORIZATION_STATE_FILE
    all_txt_files: Dict[str, Path] = {}
    for path in sorted(converted_path.rglob("*.txt")):
        if "categorized" in path.parts:
            continue
        rel_key = str(path.relative_to(converted_path))
        all_txt_files[rel_key] = path

    if not all_txt_files:
        progress("No .txt files found in converted directory. Run conversion first.")
        return {}, {}

    progress(f"Found {len(all_txt_files)} converted text files.")
    corpus_signature = _corpus_signature(all_txt_files)
    file_signatures = _file_signatures(all_txt_files)

    prior_state = _load_categorization_state(state_file)
    if prior_state and not _uses_current_taxonomy(prior_state):
        progress("Existing categorization uses an older subject taxonomy; rebuilding audit-domain categories.")
        prior_state = None

    if prior_state and prior_state.get("corpus_signature") == corpus_signature:
        prior_file_map = prior_state.get("file_map")
        if isinstance(prior_file_map, dict):
            restored_written = _restore_written_paths(categorized_dir, prior_state)
            if restored_written:
                progress("Skipped categorization (unchanged converted corpus).")
                _emit_summary(prior_file_map, restored_written, progress)
                return restored_written, prior_file_map

    if prior_state:
        prior_file_map = prior_state.get("file_map")
        prior_file_signatures = prior_state.get("file_signatures")
        prior_subjects = prior_state.get("subjects")
        if (
            isinstance(prior_file_map, dict)
            and isinstance(prior_file_signatures, dict)
            and isinstance(prior_subjects, list)
            and prior_subjects
        ):
            current_names = set(all_txt_files)
            previous_names = set(name for name in prior_file_map if isinstance(name, str))
            removed = previous_names - current_names
            changed_or_new = {
                name for name in current_names
                if prior_file_signatures.get(name) != file_signatures.get(name)
            }
            unchanged = current_names - changed_or_new
            change_threshold = max(10, int(len(all_txt_files) * 0.25))

            if len(changed_or_new) <= change_threshold:
                progress(
                    f"Incremental categorization: {len(changed_or_new)} changed/new, "
                    f"{len(removed)} removed, {len(unchanged)} unchanged."
                )
                merged_file_map: Dict[str, List[str]] = {
                    name: subjects
                    for name, subjects in prior_file_map.items()
                    if name in current_names and isinstance(subjects, list)
                }

                if changed_or_new:
                    progress("Initializing Claude AI...")
                    client = _get_claude_client()
                    changed_snippets = {
                        name: _snippet(read_text(all_txt_files[name]))
                        for name in sorted(changed_or_new)
                    }
                    _, changed_file_map = _classify_files(client, changed_snippets, prior_subjects, progress)
                    merged_file_map.update(changed_file_map)

                subject_map: Dict[str, List[str]] = {subject: [] for subject in prior_subjects}
                for filename, assigned_subjects in merged_file_map.items():
                    for subject in assigned_subjects:
                        if subject in subject_map:
                            subject_map[subject].append(filename)

                written = _write_subject_files(categorized_dir, subject_map, converted_path, all_txt_files, progress)
                _save_categorization_state(
                    state_file,
                    corpus_signature,
                    prior_subjects,
                    file_signatures,
                    merged_file_map,
                    written,
                )
                _emit_summary(merged_file_map, written, progress)
                return written, merged_file_map

    snippets = {name: _snippet(read_text(path)) for name, path in all_txt_files.items()}

    progress("Initializing Claude AI...")
    client = _get_claude_client()

    subjects = _discover_subjects(client, snippets, progress)
    progress(f"Available audit subjects ({len(subjects)}): {', '.join(subjects)}")

    subject_map, file_map = _classify_files(client, snippets, subjects, progress)
    written = _write_subject_files(categorized_dir, subject_map, converted_path, all_txt_files, progress)
    _save_categorization_state(state_file, corpus_signature, subjects, file_signatures, file_map, written)
    _emit_summary(file_map, written, progress)
    return written, file_map


def _emit_summary(file_map: Dict[str, List[str]], written: Dict[str, Path], progress: Callable):
    """Emit a formatted categorization summary table via the progress callback."""
    col_file = max((len(filename) for filename in file_map), default=20)
    col_file = min(max(col_file, 20), 60)

    sep = "-" * (col_file + 2 + 50)
    lines = [
        "",
        "=" * (col_file + 2 + 50),
        "CATEGORIZATION SUMMARY - FILE -> SUBJECT MAPPING",
        "=" * (col_file + 2 + 50),
        f"{'FILE':<{col_file}}  SUBJECT(S)",
        sep,
    ]

    for filename in sorted(file_map):
        subjects = file_map[filename]
        subject_str = ", ".join(subjects) if subjects else "(unassigned)"
        display = filename if len(filename) <= col_file else "..." + filename[-(col_file - 3):]
        lines.append(f"{display:<{col_file}}  {subject_str}")

    lines += [
        sep,
        f"Total files: {len(file_map)}   |   Subjects: {len(written)}",
        "=" * (col_file + 2 + 50),
        "",
    ]

    for line in lines:
        progress(line)


def main():
    import argparse

    configure_utf8_output()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Audit Tool - AI Subject Categorizer")
    parser.add_argument(
        "converted_dir",
        nargs="?",
        default="converted_files",
        help="Path to the converted_files directory",
    )
    args = parser.parse_args()

    try:
        written, _ = run_categorization(args.converted_dir, progress_callback=print)
        print(f"\nDone. {len(written)} subject files created.")
        for subject, path in written.items():
            print(f"  [{subject}] -> {path}")
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
