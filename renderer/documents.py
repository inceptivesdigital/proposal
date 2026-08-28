"""Reading a transcript out of a document.

People are given call notes as PDFs, Word files and text exports, and retyping
them into a box is the wrong ask. Everything here works without extra services:
PDFs through the renderer's own PDF library, .docx by reading the XML inside the
zip, and plain text as itself.
"""
import base64
import io
import re
import xml.etree.ElementTree as ET
import zipfile

MAX_BYTES = 20 * 1024 * 1024          # 20 MB, well beyond a call transcript
MAX_CHARS = 200_000

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read(filename, data):
    """filename plus raw bytes -> plain text. Raises with a plain explanation."""
    if len(data) > MAX_BYTES:
        raise ValueError("That file is larger than 20 MB.")
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        text = _pdf(data)
    elif name.endswith(".docx") or data[:2] == b"PK":
        text = _docx(data)
    elif name.endswith((".txt", ".md", ".rtf", ".vtt", ".srt", ".csv")):
        text = _plain(data, name)
    else:
        raise ValueError("Upload a PDF, a Word .docx, or a text file. "
                         "Older .doc files need saving as .docx first.")
    text = _tidy(text)
    if not text.strip():
        raise ValueError("No text could be read from that file. If it is a "
                         "scan, it needs running through OCR first.")
    return text[:MAX_CHARS]


def _pdf(data):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(io.BytesIO(data))
    out = []
    for i in range(len(doc)):
        try:
            out.append(doc[i].get_textpage().get_text_range())
        except Exception:                                     # noqa: BLE001
            continue
    return "\n".join(out)


def _docx(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist()
                 if n in ("word/document.xml",) or
                 n.startswith("word/header") or n.startswith("word/footer")]
        if "word/document.xml" not in names:
            raise ValueError("That does not look like a Word document.")
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    lines, buf = [], []
    for node in root.iter():
        tag = node.tag
        if tag == WORD_NS + "t" and node.text:
            buf.append(node.text)
        elif tag == WORD_NS + "tab":
            buf.append("\t")
        elif tag in (WORD_NS + "br", WORD_NS + "cr"):
            buf.append("\n")
        elif tag == WORD_NS + "p":
            if buf:
                lines.append("".join(buf))
                buf = []
    if buf:
        lines.append("".join(buf))
    return "\n".join(lines)


def _plain(data, name):
    for encoding in ("utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("That file's text encoding could not be read.")
    if name.endswith(".rtf"):
        text = re.sub(r"\\\\'[0-9a-f]{2}|\\\\[a-z]+-?\d* ?|[{}]", "", text)
    if name.endswith((".vtt", ".srt")):
        # subtitle exports: drop the timing lines, keep what was said
        keep = []
        for line in text.splitlines():
            s = line.strip()
            if not s or s.isdigit() or "-->" in s or s == "WEBVTT":
                continue
            keep.append(s)
        text = "\n".join(keep)
    return text


def _tidy(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # page furniture that adds nothing to a brief
    text = re.sub(r"\n\s*Page \d+( of \d+)?\s*\n", "\n", text, flags=re.I)
    return text.strip()


def read_data_url(filename, data_url):
    """The browser sends files as data URLs."""
    raw = data_url.split(",", 1)[-1]
    try:
        data = base64.b64decode(raw)
    except Exception:                                         # noqa: BLE001
        raise ValueError("That upload could not be decoded.")
    return read(filename, data)
