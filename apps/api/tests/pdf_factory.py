"""
Builds small PDFs in memory for tests, so the repo needs no binary fixtures.

Each string in `pages` becomes one page of text; an empty string gives a page
with no text layer, like a scanned document.
"""


def make_pdf(pages: list[str]) -> bytes:
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)  # PDF object numbers start at 1

    catalog = add(b"")  # placeholder, filled in once the page tree exists
    page_tree = add(b"")
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_numbers: list[int] = []
    for text in pages:
        lines = [
            line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in text.split("\n")
        ]
        stream = b"BT /F1 11 Tf 50 750 Td 14 TL " + b" ".join(
            f"({line}) '".encode() for line in lines if line
        )
        stream += b" ET"
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_numbers.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (page_tree, font, content)
            )
        )

    kids = b" ".join(b"%d 0 R" % number for number in page_numbers)
    objects[page_tree - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_numbers))
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % page_tree

    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(output)
    output += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    output += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    output += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        catalog,
        xref_at,
    )
    return bytes(output)
