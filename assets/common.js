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

  window.Lib = { repoInfo, loadLibrary, readerUrl, store, ar, titleFromFile, en, track, hits, bookPath };
})();
