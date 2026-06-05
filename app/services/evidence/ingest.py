"""Evidence ingest — upload, hash, mime, extract text, persist EvidenceItem."""
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.evidence import EvidenceItem
from app.services.evidence.keyword_classify import classify_text

_EVIDENCE_ROOT = Path("data/evidence")

# Extensions that benefit from full binary MIME detection
_TEXT_EXTS = {".txt", ".csv", ".json", ".xml", ".md", ".log"}


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_mime(filename: str, data: bytes) -> str:
    """Detect MIME using stdlib mimetypes (no libmagic dependency in tests)."""
    mime, _ = mimetypes.guess_type(filename)
    if mime:
        return mime
    # Minimal sniff for common types
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:2] in (b"PK",):
        return "application/zip"
    if data[:4] in (b"\x89PNG",):
        return "image/png"
    if data[:2] in (b"\xff\xd8",):
        return "image/jpeg"
    return "application/octet-stream"


def extract_text(path: Path, mime: str) -> str:
    """Extract readable text from a file without AI/translation overhead."""
    try:
        if mime == "application/pdf" or path.suffix.lower() == ".pdf":
            return _extract_pdf(path)
        if mime in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",) \
                or path.suffix.lower() == ".docx":
            return _extract_docx(path)
        if mime in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",) \
                or path.suffix.lower() == ".xlsx":
            return _extract_xlsx(path)
        if mime.startswith("image/") or path.suffix.lower() in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
            return _extract_image(path)
        if mime.startswith("text/") or path.suffix.lower() in _TEXT_EXTS:
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return ""


def _extract_pdf(path: Path) -> str:
    import fitz  # type: ignore
    doc = fitz.open(str(path))
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages).strip()


def _extract_docx(path: Path) -> str:
    from docx import Document  # type: ignore
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_xlsx(path: Path) -> str:
    import openpyxl  # type: ignore
    wb = openpyxl.load_workbook(str(path), data_only=True)
    rows = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                rows.append("\t".join(cells))
    return "\n".join(rows)


def _extract_image(path: Path) -> str:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        return pytesseract.image_to_string(Image.open(path)).strip()
    except Exception:
        return ""


def storage_path(project_id: str, sha256: str, filename: str) -> Path:
    ext = Path(filename).suffix
    dest_dir = _EVIDENCE_ROOT / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir / f"{sha256}{ext}"


def ingest_file(
    db: Session,
    *,
    project_id: str,
    data: bytes,
    filename: str,
    evidence_request_id: Optional[str] = None,
    uploaded_by_id: Optional[str] = None,
) -> EvidenceItem:
    sha = compute_sha256(data)
    mime = detect_mime(filename, data)

    dest = storage_path(project_id, sha, filename)
    if not dest.exists():
        dest.write_bytes(data)

    text = extract_text(dest, mime)
    category = classify_text(text, mime=mime, filename=filename)

    item = EvidenceItem(
        project_id=project_id,
        evidence_request_id=evidence_request_id,
        source_file=filename,
        sha256=sha,
        mime=mime,
        extracted_text=text or None,
        classification=category,
        reviewer_status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
