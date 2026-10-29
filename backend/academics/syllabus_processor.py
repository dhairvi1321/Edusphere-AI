"""
Syllabus text extraction and topic parsing.
Supports PDF (text-based), DOCX, and TXT files.
"""
import re
import io
import os
import zipfile

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.pptx'}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/x-pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/octet-stream',
    'text/plain',
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
QUIZ_ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}


def validate_quiz_upload(file, max_file_size=MAX_FILE_SIZE):
    """Validate quiz uploads by size, extension, signature/package, and safe decoding."""
    ext = os.path.splitext(os.path.basename(str(getattr(file, 'name', ''))))[1].lower()
    if ext not in QUIZ_ALLOWED_EXTENSIONS:
        return False, 'Unsupported file type. Choose a PDF, DOCX, or TXT syllabus.'
    size = getattr(file, 'size', None)
    if not isinstance(size, int) or size <= 0:
        return False, 'The selected file is empty.'
    if size > max_file_size:
        return False, f'The file exceeds the {max_file_size // (1024 * 1024)} MB upload limit.'
    try:
        file.seek(0)
        if ext == '.pdf':
            if not file.read(8).lstrip().startswith(b'%PDF-'):
                return False, 'The file contents do not look like a valid PDF.'
        elif ext == '.docx':
            with zipfile.ZipFile(file) as archive:
                names = set(archive.namelist())
                if '[Content_Types].xml' not in names or 'word/document.xml' not in names:
                    return False, 'The DOCX file is missing its document content.'
                if any('vbaproject' in name.casefold() for name in names):
                    return False, 'Macro-enabled documents are not accepted.'
                if sum(item.file_size for item in archive.infolist()) > max_file_size * 20:
                    return False, 'The DOCX expands beyond the safe processing limit.'
                if archive.testzip() is not None:
                    return False, 'The DOCX archive is corrupt.'
        else:
            raw = file.read()
            try:
                raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                return False, 'TXT files must use UTF-8 text encoding.'
            if not raw.decode('utf-8-sig').strip():
                return False, 'The selected file contains no text.'
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError):
        return False, 'The selected file is corrupt or cannot be read.'
    finally:
        try:
            file.seek(0)
        except (AttributeError, OSError):
            pass
    return True, None


def validate_upload(file):
    """Return (ok, error_message). Checks extension, MIME type, and size."""
    import os
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, TXT."
    mime = getattr(file, 'content_type', '') or ''
    if mime and mime not in ALLOWED_MIME_TYPES:
        return False, f"Unsupported MIME type '{mime}'."
    if file.size > MAX_FILE_SIZE:
        return False, "File exceeds the 10 MB size limit."
    return True, None


def extract_text(filepath, ext):
    """
    Extract raw text from a file at filepath.
    Returns (text, warning) where warning is non-empty for scanned PDFs.
    """
    ext = ext.lower()
    if ext == '.txt':
        with open(filepath, 'r', encoding='utf-8-sig', errors='strict') as f:
            return f.read(), None

    if ext == '.docx':
        from docx import Document
        doc = Document(filepath)
        lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                cells = [re.sub(r'\s+', ' ', cell.text).strip() for cell in row.cells]
                if any(cells):
                    lines.append(' | '.join(cells))
        text = '\n'.join(lines)
        return text, None

    if ext == '.pptx':
        from pptx import Presentation
        prs = Presentation(filepath)
        lines = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            lines.append(text)
        return '\n'.join(lines), None

    if ext == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or '')
        text = '\n'.join(pages)
        # Heuristic: if extracted text is very sparse, likely a scanned PDF
        if len(text.strip()) < 100:
            return text, (
                "This PDF appears to be scanned or image-based. "
                "Text extraction produced insufficient content. "
                "Please use a text-based PDF or convert it first."
            )
        return text, None

    return '', 'Unsupported file extension.'


# ---------------------------------------------------------------------------
# Topic parsing
# ---------------------------------------------------------------------------

# Patterns that suggest a heading / topic line
_UNIT_RE = re.compile(
    r'^(?:unit|module|chapter|section|part)\s*[-:.]?\s*(\d+|[IVXLC]+)\b',
    re.IGNORECASE,
)
_NUMBERED_RE = re.compile(r'^\s*(\d+(?:\.\d+)*)\s+(.+)')   # "1.2 Topic name"
_BULLET_RE = re.compile(r'^\s*[-•*]\s+(.+)')


def _clean(line):
    return re.sub(r'\s+', ' ', line).strip()


def _is_noise(line):
    """Skip page numbers, blank lines, very short tokens."""
    s = line.strip()
    if not s or len(s) < 3:
        return True
    if re.fullmatch(r'\d+', s):   # bare page number
        return True
    return False


def parse_topics(text, subject_name=''):
    """
    Parse extracted text into a list of topic dicts:
      {title, unit, order, confidence}
    confidence: 'high' | 'low'
    """
    lines = text.splitlines()
    topics = []
    current_unit = ''
    order = 0

    for raw in lines:
        line = _clean(raw)
        if _is_noise(line):
            continue

        # Detect unit/module headings — record but don't emit as a topic
        unit_m = _UNIT_RE.match(line)
        if unit_m:
            current_unit = line
            continue

        # Numbered topic  e.g. "1.2 Software Life Cycle"
        num_m = _NUMBERED_RE.match(line)
        if num_m:
            number, title = num_m.group(1), _clean(num_m.group(2))
            if len(title) >= 4:
                topics.append({
                    'title': title,
                    'unit': current_unit,
                    'order': order,
                    'number': number,
                    'confidence': 'high',
                })
                order += 1
            continue

        # Bullet point
        bullet_m = _BULLET_RE.match(line)
        if bullet_m:
            title = _clean(bullet_m.group(1))
            if len(title) >= 4:
                topics.append({
                    'title': title,
                    'unit': current_unit,
                    'order': order,
                    'number': '',
                    'confidence': 'high',
                })
                order += 1
            continue

        # All-caps or Title-Case short lines are likely headings
        words = line.split()
        if 2 <= len(words) <= 10:
            is_title = line.istitle() or line.isupper()
            if is_title and len(line) >= 5:
                topics.append({
                    'title': line,
                    'unit': current_unit,
                    'order': order,
                    'number': '',
                    'confidence': 'high' if is_title else 'low',
                })
                order += 1

    return topics


def _topic_heading_text(line):
    cleaned = _clean(line)
    numbered = _NUMBERED_RE.match(cleaned)
    if numbered:
        return _clean(numbered.group(2))
    bullet = _BULLET_RE.match(cleaned)
    if bullet:
        return _clean(bullet.group(1))
    return cleaned


def extract_topic_sections(text, selected_topics, max_chars=24000):
    """Return bounded syllabus sections for the selected parsed headings only."""
    lines = text.splitlines()
    detected = parse_topics(text)
    title_to_positions = {}
    for index, line in enumerate(lines):
        heading = _topic_heading_text(line).casefold()
        if any(topic['title'].casefold() == heading for topic in detected):
            title_to_positions.setdefault(heading, []).append(index)
    heading_positions = sorted(index for positions in title_to_positions.values() for index in positions)
    sections = []
    remaining = max_chars
    for topic in selected_topics:
        title = topic['title'] if isinstance(topic, dict) else topic.title
        positions = title_to_positions.get(title.casefold(), [])
        if positions:
            start = positions[0]
            end = next((position for position in heading_positions if position > start), len(lines))
            section = '\n'.join(lines[start:end]).strip()
        else:
            needle = title.casefold()
            found = next((index for index, line in enumerate(lines) if needle in line.casefold()), None)
            section = '\n'.join(lines[max(0, found - 3):found + 8]).strip() if found is not None else ''
        section = section[:min(8000, remaining)]
        if section:
            sections.append(f"Topic: {title}\n{section}")
            remaining -= len(section)
        if remaining <= 0:
            break
    return '\n\n'.join(sections)
