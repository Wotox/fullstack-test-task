import re
from dataclasses import dataclass
from pathlib import Path


SUSPICIOUS_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".js"}
MAX_SAFE_FILE_SIZE = 10 * 1024 * 1024
PDF_PAGE_MARKER = re.compile(rb"/Type\s*/Page\b")


@dataclass(frozen=True, slots=True)
class ScanResult:
    status: str
    details: str
    requires_attention: bool


@dataclass(frozen=True, slots=True)
class AlertPayload:
    level: str
    message: str


def scan_file(original_name: str, mime_type: str, size: int) -> ScanResult:
    reasons: list[str] = []
    extension = Path(original_name).suffix.lower()

    if extension in SUSPICIOUS_EXTENSIONS:
        reasons.append(f"suspicious extension {extension}")

    if size > MAX_SAFE_FILE_SIZE:
        reasons.append("file is larger than 10 MB")

    if extension == ".pdf" and mime_type not in {"application/pdf", "application/octet-stream"}:
        reasons.append("pdf extension does not match mime type")

    return ScanResult(
        status="suspicious" if reasons else "clean",
        details=", ".join(reasons) if reasons else "no threats found",
        requires_attention=bool(reasons),
    )


def extract_metadata(original_name: str, mime_type: str, size: int, stored_path: Path) -> dict:
    metadata = {
        "extension": Path(original_name).suffix.lower(),
        "size_bytes": size,
        "mime_type": mime_type,
    }

    if mime_type.startswith("text/"):
        content = stored_path.read_text(encoding="utf-8", errors="ignore")
        metadata["line_count"] = len(content.splitlines())
        metadata["char_count"] = len(content)
    elif mime_type == "application/pdf":
        content = stored_path.read_bytes()
        metadata["approx_page_count"] = max(len(PDF_PAGE_MARKER.findall(content)), 1)

    return metadata


def build_alert(processing_status: str, requires_attention: bool, scan_details: str | None) -> AlertPayload:
    if processing_status == "failed":
        return AlertPayload(level="critical", message="File processing failed")

    if requires_attention:
        return AlertPayload(
            level="warning",
            message=f"File requires attention: {scan_details}",
        )

    return AlertPayload(level="info", message="File processed successfully")
