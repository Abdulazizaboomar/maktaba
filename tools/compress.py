import pymupdf, os, sys, glob, numpy as np
src, dst = sys.argv[1], sys.argv[2]
d=pymupdf.open(src)
d.scrub(metadata=False, xml_metadata=True, attached_files=False, embedded_files=False, thumbnails=True,
        reset_fields=False, reset_responses=False, clean_pages=False, hidden_text=False, javascript=False, redactions=False, remove_links=False)
# حذف أي بيانات XMP متبقية مرتبطة بالكائنات
for x in range(1, d.xref_length()):
    try:
        if d.xref_get_key(x, "Metadata")[0] == "xref": d.xref_set_key(x, "Metadata", "null")
    except Exception: pass
d.save(dst, garbage=4, deflate=True, clean=False)
# التحقق: مقارنة كل صفحة بكسل ببكسل
a=pymupdf.open(src); b=pymupdf.open(dst); worst=0
assert a.page_count==b.page_count
for i in range(a.page_count):
    pa=a[i].get_pixmap(dpi=96); pb=b[i].get_pixmap(dpi=96)
    A=np.frombuffer(pa.samples,np.uint8).astype(int); B=np.frombuffer(pb.samples,np.uint8).astype(int)
    worst=max(worst, int(np.abs(A-B).max()) if A.shape==B.shape else 999)
ta="".join(p.get_text() for p in a); tb="".join(p.get_text() for p in b)
print(f"{os.path.basename(src)[:10]} pages={a.page_count} {os.path.getsize(src)/1e6:.1f}MB -> {os.path.getsize(dst)/1e6:.2f}MB  maxPixelDiff={worst} textSame={ta==tb}")
