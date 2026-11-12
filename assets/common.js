// أدوات مشتركة بين صفحات المكتبة
(function () {
  const BOOK_EXT = /\.pdf$/i;
  const IMG_EXT = /\.(jpe?g|png|webp)$/i;

  // استنتاج اسم الحساب والمستودع من رابط GitHub Pages تلقائياً
  function repoInfo() {
    const host = location.hostname;
    const m = host.match(/^([^.]+)\.github\.io$/i);
    if (!m) return null;
    const owner = m[1];
    const first = location.pathname.split("/").filter(Boolean)[0];
    const repo = first && !/\.html?$/i.test(first) ? first : host;
    return { owner, repo };
  }

  function titleFromFile(name) {
    return decodeURIComponent(name).replace(BOOK_EXT, "").replace(/[_-]+/g, " ").trim();
  }

  async function fetchJSON(url) {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  // يقرأ قائمة الكتب، ويضيف تلقائياً أي ملف PDF رُفع مباشرة إلى مجلد books دون تسجيله
  async function loadLibrary() {
    let data = { site: {}, books: [] };
    try { data = await fetchJSON("books.json?v=" + Date.now()); } catch (e) { console.warn("books.json", e); }
    data.site = data.site || {};
    data.books = Array.isArray(data.books) ? data.books : [];

    const info = repoInfo();
    if (info && data.site.autoDetect !== false) {
      try {
        const api = `https://api.github.com/repos/${info.owner}/${info.repo}/contents/`;
        const [bk, cv] = await Promise.all([
          fetchJSON(api + "books"),
          fetchJSON(api + "covers").catch(() => []),
        ]);
        const known = new Set(data.books.map((b) => b.file));
        const covers = {};
        (cv || []).forEach((f) => { if (IMG_EXT.test(f.name)) covers[f.name.replace(IMG_EXT, "")] = "covers/" + f.name; });
        (bk || []).forEach((f) => {
          if (f.type !== "file" || !BOOK_EXT.test(f.name)) return;
          const file = "books/" + f.name;
          if (known.has(file)) return;
          const base = f.name.replace(BOOK_EXT, "");
          data.books.push({ id: "", title: titleFromFile(f.name), file, cover: covers[base] || "", auto: true });
        });
      } catch (e) { /* القائمة الأساسية تكفي */ }
    }
    return data;
  }

  function readerUrl(b) {
    return b.id ? "read.html?id=" + encodeURIComponent(b.id) : "read.html?file=" + encodeURIComponent(b.file);
  }

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
    del(k) { try { localStorage.removeItem(k); } catch (e) {} },
  };

  const ar = (n) => Number(n).toLocaleString("ar-SA");

  // تمييز العدد بالعربية الصحيحة: [مفرد، مثنى، جمع (٣–١٠)، مفرد منصوب (١١–٩٩)، بعد المئة والألف (١٠٠، ١٠١، ٢٠٠…)]
  const WORDS = {
    book: ["كتاب", "كتابان", "كتب", "كتاباً", "كتاب"],
    page: ["صفحة", "صفحتان", "صفحات", "صفحة", "صفحة"],
    group: ["مجموعة علمية", "مجموعتان علميتان", "مجموعات علمية", "مجموعة علمية", "مجموعة علمية"],
    country: ["دولة", "دولتان", "دول", "دولة", "دولة"],
    visitor: ["زائر", "زائران", "زوار", "زائراً", "زائر"],
    view: ["مشاهدة", "مشاهدتان", "مشاهدات", "مشاهدة", "مشاهدة"],
    surah: ["سورة", "سورتان", "سور", "سورة", "سورة"],
    list: ["قائمة تشغيل", "قائمتا تشغيل", "قوائم تشغيل", "قائمة تشغيل", "قائمة تشغيل"],
    acat: ["تصنيف صوتي", "تصنيفان صوتيان", "تصنيفات صوتية", "تصنيفاً صوتياً", "تصنيف صوتي"],
    lesson: ["مقطع", "مقطعان", "مقاطع", "مقطعاً", "مقطع"],
    category: ["تصنيف", "تصنيفان", "تصنيفات", "تصنيفاً", "تصنيف"],
    work: ["مؤلَّف جديد", "مؤلَّفان جديدان", "مؤلفات جديدة", "مؤلَّفاً جديداً", "مؤلَّف جديد"],
  };
  function plural(n, w) {
    const f = WORDS[w] || w; n = Math.abs(Math.round(Number(n) || 0)); const m = n % 100;
    if (n === 1) return f[0];
    if (n === 2) return f[1];
    if (n >= 100 && m <= 2) return f[4];
    if (m >= 11) return f[3];
    return f[2];
  }

  // ===== العدادات (GoatCounter) — إن تعطلت الخدمة يعمل الموقع عادياً وتختفي الأرقام فقط =====
  const isLocal = () => /^(localhost|127\.|0\.0\.0\.0|\[::1\])/.test(location.hostname) || location.protocol === "file:";
  const en = (n) => Number(n).toLocaleString("en-US");
  function gcBase(code) {
    code = (code || "").trim();
    if (!code) return "";
    if (/^https?:\/\//.test(code)) return code.replace(/\/+$/, "");
    return "https://" + code + ".goatcounter.com";
  }
  // تسجيل زيارة لمسار معيّن — عبر سكربت GoatCounter الرسمي، مع بديل احتياطي
  let gcLoading = null;
  function loadGC(base) {
    if (window.goatcounter && window.goatcounter.count) return Promise.resolve(window.goatcounter);
    if (gcLoading) return gcLoading;
    window.goatcounter = Object.assign(window.goatcounter || {}, { no_onload: true });
    gcLoading = new Promise((ok, no) => {
      const sc = document.createElement("script");
      sc.async = true; sc.src = "https://gc.zgo.at/count.js";
      sc.setAttribute("data-goatcounter", base + "/count");
      sc.setAttribute("data-goatcounter-settings", JSON.stringify({ no_onload: true }));
      sc.onload = () => (window.goatcounter && window.goatcounter.count ? ok(window.goatcounter) : no());
      sc.onerror = no;
      document.head.appendChild(sc);
      setTimeout(no, 8000);
    });
    return gcLoading;
  }
  function track(code, path, title) {
    const base = gcBase(code); if (!base || isLocal()) return;
    loadGC(base).then((gc) => gc.count({ path, title: title || document.title, event: false }))
      .catch(() => {
        try {
          const q = new URLSearchParams({ p: path, t: title || document.title, r: document.referrer || "", s: String(screen.width || ""), rnd: Math.random().toString(36).slice(2) });
          new Image().src = base + "/count?" + q.toString();
        } catch (e) {}
      });
  }
  // قراءة العدد العام لمسار (أو TOTAL لكل الموقع)
  async function hits(code, path, from) {
    const base = gcBase(code); if (!base) return null;
    try {
      // نحدد فترة زمنية (من بداية المكتبة إلى الغد) لأن الرابط بدونها يُرجع نسخة مؤقتة قديمة
      const end = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
      const url = base + "/counter/" + (path === "TOTAL" ? "TOTAL" : encodeURIComponent(path)) + ".json";
      // تاريخ البداية يتغيّر كل 10 دقائق (قبل إنشاء المكتبة دائماً) فلا يُرجع GoatCounter نسخة محفوظة قديمة
      const slot = Math.floor(Date.now() / 600000) % 700;
      const start = new Date(Date.UTC(2026, 0, 1) - slot * 86400000).toISOString().slice(0, 10);
      let q = "?start=" + start + "&end=" + end;
      // فترة محددة (مثل آخر 28 يوماً): نغيّر تاريخ النهاية المستقبلي كل 10 دقائق لنفس السبب
      if (from) q = "?start=" + from + "&end=" + new Date(Date.now() + (1 + slot) * 86400000).toISOString().slice(0, 10);
      let r = await fetch(url + q, { cache: "no-store" });
      if (!r.ok && r.status !== 404) r = await fetch(url + "?start=" + (from || "2026-01-01"), { cache: "no-store" });
      if (r.status === 404) return 0;
      if (!r.ok) return null;
      const j = await r.json();
      const n = parseInt(String(j.count ?? "").replace(/[^0-9]/g, ""), 10);
      return isNaN(n) ? null : n;
    } catch (e) { return null; }
  }
  const bookPath = (b) => "/book/" + (b.id || (b.file || "").replace(/^books\//, "").replace(/\.pdf$/i, ""));

  // ===== v39: الصوتيات والمرئيات =====
  // ملفات عنصر في archive.org (الأصلية فقط) — قراءة مباشرة من API العام، مع ذاكرة 10 دقائق
  async function iaFiles(item) {
    item = String(item || "").trim().replace(/^https?:\/\/archive\.org\/(details|download)\//, "").split(/[/?#]/)[0];
    if (!item) return [];
    const key = "ia:" + item;
    try { const c = JSON.parse(sessionStorage.getItem(key) || "null"); if (c && Date.now() - c.t < 600000) return c.f; } catch (e) {}
    const r = await fetch("https://archive.org/metadata/" + encodeURIComponent(item) + "/files", { cache: "no-store" });
    if (!r.ok) throw new Error("ia " + r.status);
    const j = await r.json(); const list = Array.isArray(j) ? j : (j.result || j.files || []);
    const f = list.filter((x) => x && x.source === "original" && /\.(mp3|m4a|ogg|opus|wav)$/i.test(x.name || ""))
      .map((x) => ({ name: x.name, title: String(x.title || x.name).replace(/\.[^.]+$/, ""), length: +x.length || 0,
        url: "https://archive.org/download/" + encodeURIComponent(item) + "/" + String(x.name).split("/").map(encodeURIComponent).join("/") }))
      .sort((a, b) => a.name.localeCompare(b.name, "ar", { numeric: true }));
    try { sessionStorage.setItem(key, JSON.stringify({ t: Date.now(), f })); } catch (e) {}
    return f;
  }
  // معرّف قائمة تشغيل يوتيوب من رابط كامل أو معرّف مباشر
  const ytList = (v) => { v = String(v || "").trim(); const m = v.match(/[?&]list=([\w-]+)/); return m ? m[1] : (/^[\w-]{10,}$/.test(v) ? v : ""); };
  // إعدادات الوسائط من books.json ← media { quran, videos: [{title, playlist}], audio: [{title, item}] }
  function mediaOf(data) {
    const m = (data && data.media) || {};
    const videos = (m.videos || []).map((v) => ({ title: String(v.title || "").trim(), list: ytList(v.playlist || v.list) })).filter((v) => v.title && v.list);
    const audio = (m.audio || []).map((a) => ({ title: String(a.title || "").trim(), item: String(a.item || "").trim() })).filter((a) => a.title && a.item);
    return { quran: String(m.quran || "").trim(), videos, audio, preview: !!m.preview };
  }

  window.Lib = { repoInfo, loadLibrary, readerUrl, store, ar, plural, iaFiles, ytList, mediaOf, titleFromFile, en, track, hits, bookPath };
})();
