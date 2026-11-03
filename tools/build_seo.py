#!/usr/bin/env python3
"""
الظهور في محركات البحث ونماذج الذكاء الاصطناعي (v37) — مكتبة د. عبد العزيز بن سعيد بن غائب (ألوان المكتبة الخاصة في style.css و home.css)
يولّد من books.json وملفات PDF:
  1) kitab/<id>.html  صفحة نصية ثابتة لكل كتاب (تُحذف صفحة أي كتاب انحذف)
  2) قسم ثابت في index.html بين <!-- SEO:START --> و <!-- SEO:END -->
  3) sitemap.xml   4) llms.txt
التشغيل:  python3 tools/build_seo.py [رابط-الموقع]
(يشتغل تلقائياً عبر .github/workflows/seo.yml مع كل تغيير في books.json أو مجلد books)
"""
import datetime, html, json, os, re, sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

# ---------- أدوات ----------
e = lambda s: html.escape(str(s or ""), quote=True)
plain = lambda s: re.sub(r"[ً-ْٰ]", "", str(s or "")).strip()
AR_DIG = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
ar = lambda n: f"{int(n):,}".replace(",", "٬").translate(AR_DIG)
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
def ar_date(s):
    try: d = datetime.date.fromisoformat(str(s)[:10])
    except Exception: return ""
    return f"{ar(d.day)} {MONTHS[d.month - 1]} {str(d.year).translate(AR_DIG)}م"
# نفس قاعدة Lib.plural في common.js
WORDS = {"book": ["كتاب", "كتابان", "كتب", "كتاباً", "كتاب"], "page": ["صفحة", "صفحتان", "صفحات", "صفحة", "صفحة"]}
def plural(n, w):
    f = WORDS[w]; n = abs(round(float(n or 0))); m = n % 100
    if n == 1: return f[0]
    if n == 2: return f[1]
    if n >= 100 and m <= 2: return f[4]
    if m >= 11: return f[3]
    return f[2]
def count(n, w):  # «٣٧ صفحة» — «صفحة واحدة» — «صفحتان»
    n = int(n)
    if n == 1: return {"book": "كتاب واحد", "page": "صفحة واحدة"}[w]
    if n == 2: return plural(2, w)
    return f"{ar(n)} {plural(n, w)}"

def names(site):
    """اسم المكتبة واسم المؤلف من books.json.
    - المكتبة: site.libraryName، وإلا «brandTitle لـbrandSub» إذا كان سطر الشعار يبدأ بـ«مؤلفات»، وإلا العنوان.
    - المؤلف: site.authorName، وإلا site.author بدون «مؤلفات» في أوله. واسم الشخص في JSON-LD بدون اللقب."""
    bt, bs_ = plain(site.get("brandTitle")), plain(site.get("brandSub"))
    lib = plain(site.get("libraryName")) or (f"{bt} ل{bs_}" if bt and bs_.startswith("مؤلفات") else "") or plain(site.get("title")) or bt or "المكتبة"
    au = plain(site.get("authorName")) or re.sub(r"^(مؤلفات|كتب|رسائل ومؤلفات)\s*[:：]?\s*", "", plain(site.get("author")))
    return lib, au
def sub_(site):  # الوصف بدون علامة الترقيم الأخيرة حتى لا تتكرر مع «:» و«—»
    return re.sub(r"[\s.،:؛]+$", "", str(site.get("subtitle") or "")) or "مكتبة رقمية"
def person(name):  # «الشيخ سلطان…» ← «سلطان…»
    return re.sub(r"^(الإمام|الشيخ|فضيلة الشيخ|الدكتور|الأستاذ|أ\.د\.|د\.|أ\.)\s*", "", name or "").strip()

def base_url():
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"): u = sys.argv[1]
    elif os.environ.get("GITHUB_REPOSITORY"):
        o, r = os.environ["GITHUB_REPOSITORY"].split("/", 1)
        u = f"https://{o.lower()}.github.io/" + ("" if r.lower() == f"{o.lower()}.github.io" else r + "/")
    else:
        m = re.search(r'<link rel="canonical" href="([^"]+)"', Path("index.html").read_text(encoding="utf-8"))
        if not m: sys.exit("اكتب رابط الموقع: python3 tools/build_seo.py https://USER.github.io/REPO/")
        u = m.group(1)
    return u.rstrip("/") + "/"

# ---------- مقتطف من محتوى الكتاب (فقط إذا النص المستخرج سليم) ----------
# خطوط PDF العربية كثيراً ما تُخرج نصاً مشوّهاً (اهلل بدل الله، يف بدل في، األوىل…)؛ إذا ظهر أي أثر لذلك لا نضع شيئاً.
BAD = re.compile(r"اهلل|هلل|عبدهللا|األ|اإل|اآل|(?<!\S)يف(?!\S)|ىل(?!\S)|ىن(?!\S)|[�åﭐ-﷿ﹰ-﻿-]")
def excerpt(pdf):
    try: import pymupdf
    except ImportError:
        try: import fitz as pymupdf
        except ImportError: return None
    try:
        doc = pymupdf.open(pdf)
        pages = [doc[i].get_text() for i in range(min(8, len(doc)))]
    except Exception: return None
    raw = "\n".join(pages)
    words = re.findall(r"[ء-ي]{2,}", raw)
    if len(words) < 60 or BAD.search(raw): return None
    # لا نقبل نصاً معكوس الأسطر أو مقطّع الحروف: معظم الكلمات لازم تكون كلمات عربية طبيعية
    if sum(len(w) == 1 for w in re.findall(r"[ء-ي]+", raw)) > 0.08 * len(words): return None
    clean = lambda s: re.sub(r"\s+", " ", re.sub(r"[ـ‎‏‪-‮]", "", s)).strip()
    toc, intro = [], []
    for p in pages[1:]:
        lines = [clean(x) for x in p.splitlines()]
        lines = [x for x in lines if x and not re.fullmatch(r"[\d٠-٩\s.\-–*]+", x)]
        if any(re.search(r"^(الفهرس|فهرس|المحتويات|فهرس الموضوعات)$", x) for x in lines):
            for x in lines:
                t = clean(re.sub(r"[.\s…]*[\d٠-٩]+\s*$", "", x))
                if t and t not in ("الفهرس", "فهرس", "المحتويات", "فهرس الموضوعات") and len(t) <= 70 and t not in toc: toc.append(t)
        else:
            intro.extend(x for x in lines if x not in intro)
    text = clean(" ".join(intro))
    if len(text) > 1500:
        cut = text[:1500]; k = max(cut.rfind("."), cut.rfind("،"), cut.rfind(" "))
        text = cut[:k if k > 1000 else 1500].rstrip(" ،") + "…"
    if len(text) < 120 and not toc: return None
    return {"intro": text, "toc": toc[:40]}

# ---------- القوالب ----------
def size(path):  # أبعاد الغلاف الحقيقية حتى لا تتحرك الصفحة أثناء التحميل
    try:
        from PIL import Image
        w, h = Image.open(path).size; return f' width="{w}" height="{h}"'
    except Exception: return ""
BRAND_SVG = '<svg viewBox="0 0 64 64" aria-hidden="true"><path d="M10 22c8-3.5 15-2.5 22 2.5v27c-7-5-14-6-22-2.5z M54 22c-8-3.5-15-2.5-22 2.5v27c7-5 14-6 22-2.5z" fill="#c6a15b"/><path d="M32 7l2.4 4.9 5.4.8-3.9 3.8.9 5.4L32 19.4l-4.8 2.5.9-5.4-3.9-3.8 5.4-.8z" fill="#f7f3e8"/></svg>'  # نفس شعار رأس الموقع
CREDIT = '<div class="credit">تصميم وإعداد: <b>محمد الشهري</b><span class="sep">•</span>للتواصل: <a href="https://wa.me/966564824329" target="_blank" rel="noopener" dir="ltr">0564824329</a></div>'
PAGE_CSS = """
body.kb-page{display:flex;flex-direction:column;min-height:100vh}.kb-page .kb{flex:1}
.kb{padding:40px 0 8px}
.kb-info{max-width:640px}
.kb .crumb{font-size:14px;color:var(--muted);margin:0 0 22px}
.kb .crumb a{color:var(--gold);text-decoration:none;font-weight:600}
.kb-grid{display:grid;grid-template-columns:minmax(0,300px) minmax(0,1fr);gap:44px;align-items:start}
.kb-cover{margin:0;border-radius:6px 14px 14px 6px;overflow:hidden;background:var(--card);box-shadow:0 22px 44px -22px color-mix(in srgb,var(--emerald-dd) 55%,transparent),0 0 0 1px var(--line)}
.kb-cover img{display:block;width:100%;height:auto}
.kb h1{font-family:var(--display);font-weight:700;font-size:clamp(34px,5vw,52px);line-height:1.45;color:var(--emerald);margin:0 0 6px}
.kb .by{font-size:17px;color:var(--gold);margin:0 0 22px;font-weight:500}
.kb .by:has(+.rev){margin-bottom:4px}.kb .by.rev{font-size:15px;color:var(--muted)}
.kb dl{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px 18px;margin:0 0 28px;padding:18px 20px;background:var(--card);border:1px solid var(--line);border-radius:var(--r)}
.kb dt{color:var(--muted);font-size:14.5px}
.kb dd{margin:0;font-weight:600;color:var(--ink)}
.kb dd a{color:inherit;text-decoration:none}
.kb .desc{line-height:2;margin:0 0 26px}
.kb-act{display:flex;flex-wrap:wrap;gap:12px 18px;align-items:center}
.kb-read{display:inline-flex;align-items:center;gap:10px;background:var(--emerald);color:#fff;text-decoration:none;font-weight:600;font-size:17px;padding:14px 28px;border-radius:999px;box-shadow:0 12px 26px -12px color-mix(in srgb,var(--emerald) 70%,transparent);transition:background .2s,transform .2s}
.kb-read:hover{background:var(--emerald-d);transform:translateY(-1px)}
.kb-read svg{width:20px;height:20px}
.kb-back{color:var(--gold);font-weight:600;text-decoration:none}
.kb-back:hover{text-decoration:underline}
.kb-ex{margin:44px 0 0;padding:26px 28px;background:var(--card);border:1px solid var(--line);border-radius:var(--r)}
.kb-ex h2{font-family:var(--display);color:var(--emerald);font-size:26px;margin:0 0 12px}
.kb-ex h3{font-size:16px;color:var(--gold);margin:20px 0 8px}
.kb-ex p{line-height:2.1;margin:0}
.kb-ex ul{margin:0;padding-inline-start:20px;columns:2;column-gap:32px;line-height:2}
.kb-foot{margin-top:56px;background:var(--emerald-dd)}
@media (max-width:760px){.kb{padding-top:24px}.kb-grid{grid-template-columns:minmax(0,1fr);gap:26px;text-align:center}.kb-cover{max-width:230px;margin:0 auto}
  .kb dl{text-align:start}.kb-act{justify-content:center}.kb-ex{text-align:start;padding:20px 18px}.kb-ex ul{columns:1}.kb-foot .foot-bot{padding-bottom:22px}}
"""

def brand_txt(site, lib, base):  # الشعار: سطران، أو اسم المؤلف بالخط اليدوي (site.nameArt) ملوّناً بالهوية
    bt, bs_ = site.get("brandTitle") or lib, site.get("brandSub") or site.get("author") or ""
    if site.get("nameArt"):
        return (f'<span class="brand-txt has-art"><b class="sr">{e(bt)}</b><small class="sr">{e(bs_)}</small>'
                f'<span class="name-art" role="img" aria-label="{e(bs_)}" style="--na:url(&quot;{e(base + site["nameArt"])}&quot;)"></span></span>')
    return f'<span class="brand-txt"><b>{e(bt)}</b><small>{e(bs_)}</small></span>'

def book_page(b, site, lib, site_author, base, theme, ver, ex):
    title, author, cat = b["title"], (b.get("author") or site_author or "").strip(), (b.get("category") or "").strip()
    url, cover = f"{base}kitab/{quote(b['id'])}.html", (base + quote(b["cover"], safe="/?=&")) if b.get("cover") else base + "assets/og.jpg"
    pages = int(b.get("pages") or 0); desc_field = (b.get("description") or b.get("desc") or "").strip()
    rev = (b.get("reviewer") or "").strip()  # «مراجعة وتعليق» مثل نونية القحطاني
    head_title = f"{title} — {author} | {lib}" if author else f"{title} | {lib}"
    meta = f"كتاب «{title}»" + (f" — {author}" if author else "") + (f"، مراجعة وتعليق {rev}" if rev else "") + (f"، من تصنيف {cat}" if cat else "") + (f"، في {count(pages, 'page')}" if pages else "") + f". اقرأه مجاناً بتقليب الصفحات في {lib}."
    if desc_field: meta = desc_field + " — " + meta
    ld = {"@context": "https://schema.org", "@type": "Book", "name": title, "inLanguage": "ar", "url": url, "image": cover,
          "isPartOf": {"@type": "WebSite", "name": lib, "url": base}}
    if author: ld["author"] = {"@type": "Person", "name": person(author)}
    if rev: ld["editor"] = {"@type": "Person", "name": person(rev)}
    if pages: ld["numberOfPages"] = pages
    if cat: ld["genre"] = cat
    if desc_field: ld["description"] = desc_field
    if b.get("added"): ld["dateCreated"] = str(b["added"])[:10]
    ld_json = json.dumps(ld, ensure_ascii=False, indent=1).replace("</", "<\\/")
    rows = []
    if author: rows.append(("المؤلف", e(author)))
    if rev: rows.append(("مراجعة وتعليق", e(rev)))
    if cat: rows.append(("التصنيف", f'<a href="../#library">{e(cat)}</a>'))
    if pages: rows.append(("عدد الصفحات", e(count(pages, "page"))))
    if b.get("added") and ar_date(b["added"]): rows.append(("تاريخ الإضافة", f'<time datetime="{e(str(b["added"])[:10])}">{ar_date(b["added"])}</time>'))
    dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    exh = ""
    if ex:
        exh = '<section class="kb-ex" aria-labelledby="exT"><h2 id="exT">من محتوى الكتاب</h2>'
        if ex["intro"]: exh += f"<p>{e(ex['intro'])}</p>"
        if ex["toc"]: exh += "<h3>من موضوعات الكتاب</h3><ul>" + "".join(f"<li>{e(t)}</li>" for t in ex["toc"]) + "</ul>"
        exh += "</section>"
    read = f"../read.html?id={quote(b['id'])}"
    style = ""  # لا يوجد site.theme في هذي المكتبة
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(head_title)}</title>
<meta name="description" content="{e(meta)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="book">
<meta property="og:locale" content="ar_SA">
<meta property="og:site_name" content="{e(lib)}">
<meta property="og:title" content="{e(title + (' — ' + author if author else ''))}">
<meta property="og:description" content="{e(meta)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(cover)}">
<meta property="og:image:alt" content="{e(title)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(meta)}">
<meta name="twitter:image" content="{e(cover)}">
<script type="application/ld+json">
{ld_json}
</script>
<link rel="apple-touch-icon" href="../assets/apple-touch-icon.png">
<link rel="stylesheet" href="../assets/style.css?v={ver[0]}">
<link rel="stylesheet" href="../assets/home.css?v={ver[1]}">
{style}<style>{PAGE_CSS.strip()}</style>
</head>
<body class="home kb-page">
<header class="topbar">
  <div class="wrap">
    <a class="brand" href="../" aria-label="الصفحة الرئيسية">
      <span class="brand-mark">{BRAND_SVG}</span>
      {brand_txt(site, lib, base)}
    </a>
  </div>
</header>
<main class="kb">
  <div class="wrap">
    <p class="crumb"><a href="../">{e(lib)}</a>{' ‹ ' + e(cat) if cat else ''}</p>
    <article class="kb-grid">
      <figure class="kb-cover"><img src="../{e(b.get('cover') or 'assets/og.jpg')}" alt="{e(title)}"{size((b.get('cover') or '').split('?')[0])}></figure>
      <div class="kb-info">
        <h1>{e(title)}</h1>
        {f'<p class="by">{e(author)}</p>' if author else ''}{f'<p class="by rev">مراجعة وتعليق: {e(rev)}</p>' if rev else ''}
        {f'<p class="desc">{e(desc_field)}</p>' if desc_field else ''}
        <dl>{dl}</dl>
        <div class="kb-act">
          <a class="kb-read" href="{e(read)}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 5.5C5 4 8.5 4.2 12 6.5v13c-3.5-2.3-7-2.5-10-1z M22 5.5C19 4 15.5 4.2 12 6.5v13c3.5-2.3 7-2.5 10-1z"/></svg>اقرأ الكتاب</a>
          <a class="kb-back" href="../">العودة للمكتبة ←</a>
        </div>
      </div>
    </article>
    {exh}
  </div>
</main>
<footer class="foot kb-foot"><div class="foot-bot"><div class="wrap">{CREDIT}</div></div></footer>
</body>
</html>
"""

def cats_of(b): return [c for c in [b.get("category") or ""] + list(b.get("alsoIn") or []) if c] or [""]

def seo_block(site, lib, author, books, cats):
    # قائمة ثابتة داخل <noscript> في مكان رف الكتب (#shelf): تظهر لمن لا يشغّل الجافاسكربت ولقرّاء HTML (نماذج الذكاء الاصطناعي)،
    # ولا تُرسم إطلاقاً للزائر العادي — بدون أي إخفاء بالـ CSS وبدون وميض.
    L = ['<!-- SEO:START (يُولَّد تلقائياً: python3 tools/build_seo.py — لا تعدّل هنا) -->',
         '<noscript>',
         '<style>#shelf>noscript{display:block;grid-column:1/-1}.seo-ns{line-height:1.9}.seo-ns h2{font-family:var(--display);color:var(--emerald);margin:0 0 6px}.seo-ns h3{color:var(--gold);margin:22px 0 6px;font-size:18px}.seo-ns ul{margin:0;padding-inline-start:22px}.seo-ns a{color:var(--ink)}</style>',
         '<section class="seo-ns" aria-label="قائمة الكتب">',
         f'<h2>{e(lib)}{" — " + e(author) if author and person(author) not in lib else ""}</h2>',
         f'<p>{e(sub_(site))}: {e(count(len(books), "book"))} تُقرأ مجاناً بتقليب الصفحات على الجوال والكمبيوتر.</p>']
    for c in cats:
        L.append(f'<h3>{e(c or "أخرى")}</h3><ul>' + "".join(f'<li><a href="kitab/{quote(b["id"])}.html">{e(b["title"])}</a></li>' for b in books if c in cats_of(b)) + "</ul>")
    L += ['</section>', '</noscript>', '<!-- SEO:END -->']
    return "\n".join(L)

def put(name, text):  # لا نكتب الملف إلا إذا تغيّر محتواه
    p = Path(name)
    if not p.exists() or p.read_text(encoding="utf-8") != text: p.write_text(text, encoding="utf-8")

def main():
    data = json.loads(Path("books.json").read_text(encoding="utf-8"))
    site = data.get("site") or {}
    books = [b for b in data.get("books") or [] if b.get("id") and b.get("title") and re.fullmatch(r"[\w-]+", b["id"])]
    base = base_url()
    lib, author = names(site)
    theme = ""
    idx = Path("index.html").read_text(encoding="utf-8")
    v1 = re.search(r'assets/style\.css\?v=(\d+)', idx); v2 = re.search(r'assets/home\.css\?v=(\d+)', idx)
    ver = (v1.group(1) if v1 else "1", v2.group(1) if v2 else (v1.group(1) if v1 else "1"))
    # التصنيفات بنفس ترتيب الموقع، ثم أي تصنيف غير مسجّل، ثم «أخرى»
    cats = [c for c in site.get("categories") or [] if any((b.get("category") or "") == c for b in books)]
    cats += sorted({b.get("category") or "" for b in books} - set(cats) - {""})
    if any(not b.get("category") for b in books): cats.append("")
    # 1) صفحات الكتب
    out = Path("kitab"); out.mkdir(exist_ok=True)
    keep, n_ex = set(), 0
    for b in books:
        ex = excerpt(b["file"]) if b.get("file") and Path(b["file"]).exists() else None
        n_ex += bool(ex)
        p = out / f"{b['id']}.html"; keep.add(p.name)
        s = book_page(b, site, lib, author, base, theme, ver, ex)
        if not p.exists() or p.read_text(encoding="utf-8") != s: p.write_text(s, encoding="utf-8")
    removed = [p.name for p in out.glob("*.html") if p.name not in keep]
    for name in removed: (out / name).unlink()
    # 2) القائمة الثابتة في index.html: داخل رف الكتب <main id="shelf"> (يستبدلها العرض المعتاد للزائر)
    blk = seo_block(site, lib, author, books, cats)
    new = re.sub(r"\n?<!-- SEO:START.*?<!-- SEO:END -->\n?", "", idx, flags=re.S)  # إزالة أي نسخة سابقة أينما كانت
    m = re.search(r'(<main class="shelf" id="shelf"[^>]*>)(</main>)', new)
    if not m: sys.exit('لم أجد <main class="shelf" id="shelf"> فارغاً في index.html')
    new = new[:m.end(1)] + "\n" + blk + "\n" + new[m.start(2):]
    if new != idx: Path("index.html").write_text(new, encoding="utf-8")
    # 3) sitemap.xml
    day = lambda b: str(b.get("added") or b.get("date") or "")[:10]
    last = max([day(b) for b in books if day(b)] or [datetime.date.today().isoformat()])
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
          f"  <url><loc>{e(base)}</loc><lastmod>{last}</lastmod></url>"]
    sm += [f"  <url><loc>{e(base)}kitab/{quote(b['id'])}.html</loc>" + (f"<lastmod>{day(b)}</lastmod>" if day(b) else "") + "</url>" for b in books]
    sm.append("</urlset>")
    put("sitemap.xml", "\n".join(sm) + "\n")
    # 4) llms.txt
    au2 = author if author and person(author) not in lib else ""  # لا نكرر الاسم إذا كان جزءاً من اسم المكتبة
    lt = [f"# {lib}" + (f" — {au2}" if au2 else ""), "",
          f"> {sub_(site)}{' — ' + au2 if au2 else ''}، فيها {count(len(books), 'book')} باللغة العربية.",
          "> تُقرأ الكتب مجاناً على الموقع بتقليب الصفحات؛ ولكل كتاب صفحة فيها بياناته ورابط قراءته.", "",
          f"- الموقع: {base}"]
    for c in cats:
        lt += ["", f"## {c or 'أخرى'}", ""]
        for b in books:
            if c not in cats_of(b): continue
            info = [x for x in [b.get("author") if b.get("author") and b.get("author") != author else "", ("مراجعة وتعليق " + b["reviewer"]) if b.get("reviewer") else "", c, count(b["pages"], "page") if b.get("pages") else ""] if x]
            lt.append(f"- [{b['title']}]({base}kitab/{quote(b['id'])}.html): " + "، ".join(info))
    put("llms.txt", "\n".join(lt) + "\n")
    print(f"✓ {len(books)} صفحة كتاب في kitab/ (مع مقتطف: {n_ex})" + (f" — حُذفت: {', '.join(removed)}" if removed else ""))
    print(f"✓ index.html (قسم SEO) • sitemap.xml • llms.txt — {base}")

if __name__ == "__main__":
    main()
