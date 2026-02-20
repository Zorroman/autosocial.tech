
// API base:
// - local override: localStorage.apiBase
// - localhost dev:  http://127.0.0.1:5000
// - production:     https://api.<root-domain>
const _host = window.location.hostname || '';
const _isLocal = _host === 'localhost' || _host === '127.0.0.1';
const _rootHost = _host.replace(/^www\./, '');
const _savedApiBaseRaw = (localStorage.getItem('apiBase') || '').trim();
const _savedApiBase = _savedApiBaseRaw.replace(/\/+$/, '');
const _savedApiHost = (() => {
  if (!_savedApiBase) return '';
  try {
    return new URL(_savedApiBase).hostname.toLowerCase();
  } catch {
    return '';
  }
})();
const _savedApiAllowed = _isLocal
  ? /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(_savedApiBase)
  : /^api(-dev)?\.autosocial\.tech$/i.test(_savedApiHost);
const _defaultApiBase = _isLocal
  ? 'http://127.0.0.1:5000'
  : `${window.location.protocol}//api.${_rootHost}`;
const API_BASE = _savedApiAllowed ? _savedApiBase : _defaultApiBase;
const state = {
  token: localStorage.getItem('token') || '',
  theme: localStorage.getItem('theme') || 'light',
  authMode: 'register',
  authProviders: null,
  user: null,
  billing: null,
  projects: [],
  connections: [],
  connectionPicker: {
    open: false,
    connectionId: null,
    loading: false,
    pages: [],
    selectedPageId: '',
    error: '',
    filter: 'all', // all | with_ig | without_ig
    query: '',
  },
  posts: [],
  plans: [],
  blog: [],
  adminUsers: [],
  adminRevenue: null,
  notice: null,
  createWizard: {
    step: 1,
    projectId: '',
    category: 'business',
    topic: '',
    tone: 'friendly',
    language: 'ru',
    previewText: '',
    mode: 'now',
    scheduleAt: '',
    platforms: { facebook: true, instagram: true },
    mediaUrl: '',
  },
};

const CP1251_EXTRA_MAP = {
  0x0402: 0x80, 0x0403: 0x81, 0x201A: 0x82, 0x0453: 0x83, 0x201E: 0x84, 0x2026: 0x85, 0x2020: 0x86, 0x2021: 0x87,
  0x20AC: 0x88, 0x2030: 0x89, 0x0409: 0x8A, 0x2039: 0x8B, 0x040A: 0x8C, 0x040C: 0x8D, 0x040B: 0x8E, 0x040F: 0x8F,
  0x0452: 0x90, 0x2018: 0x91, 0x2019: 0x92, 0x201C: 0x93, 0x201D: 0x94, 0x2022: 0x95, 0x2013: 0x96, 0x2014: 0x97,
  0x2122: 0x99, 0x0459: 0x9A, 0x203A: 0x9B, 0x045A: 0x9C, 0x045C: 0x9D, 0x045B: 0x9E, 0x045F: 0x9F, 0x00A0: 0xA0,
  0x040E: 0xA1, 0x045E: 0xA2, 0x0408: 0xA3, 0x00A4: 0xA4, 0x0490: 0xA5, 0x00A6: 0xA6, 0x00A7: 0xA7, 0x0401: 0xA8,
  0x00A9: 0xA9, 0x0404: 0xAA, 0x00AB: 0xAB, 0x00AC: 0xAC, 0x00AD: 0xAD, 0x00AE: 0xAE, 0x0407: 0xAF, 0x00B0: 0xB0,
  0x00B1: 0xB1, 0x0406: 0xB2, 0x0456: 0xB3, 0x0491: 0xB4, 0x00B5: 0xB5, 0x00B6: 0xB6, 0x00B7: 0xB7, 0x0451: 0xB8,
  0x2116: 0xB9, 0x0454: 0xBA, 0x00BB: 0xBB, 0x0458: 0xBC, 0x0405: 0xBD, 0x0455: 0xBE, 0x0457: 0xBF,
};
const UTF8_DECODER = new TextDecoder('utf-8', { fatal: true });

function cp1251ByteForChar(ch) {
  const code = ch.charCodeAt(0);
  // ASCII must stay untouched; decode only mojibake-like Cyrillic segments.
  if (code <= 0x7F) return null;
  // Preserve C1 controls that often appear in mojibake pairs like "\u0420\u0098".
  if (code >= 0x80 && code <= 0x9F) return code;
  if (code >= 0x0410 && code <= 0x044F) return code - 0x0350;
  if (Object.prototype.hasOwnProperty.call(CP1251_EXTRA_MAP, code)) return CP1251_EXTRA_MAP[code];
  return null;
}

function decodeMojibake(value) {
  const source = String(value ?? '');
  if (!source) return source;
  let out = '';
  let bufChars = '';
  let bufBytes = [];
  const flush = () => {
    if (!bufBytes.length) return;
    try {
      const decoded = UTF8_DECODER.decode(new Uint8Array(bufBytes));
      out += decoded.includes('\uFFFD') ? bufChars : decoded;
    } catch {
      out += bufChars;
    }
    bufChars = '';
    bufBytes = [];
  };

  for (const ch of source) {
    const b = cp1251ByteForChar(ch);
    if (b === null) {
      flush();
      out += ch;
      continue;
    }
    bufChars += ch;
    bufBytes.push(b);
  }
  flush();
  return out;
}

const esc = (v) => decodeMojibake(String(v ?? '')).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const safeText = (v, fallback = '—') => {
  const s = String(v ?? '').replace(/\uFFFD/g, '').trim();
  return s ? s : fallback;
};
const isAuthRoute = (p) => p !== '/login';
let renderVersion = 0;

function setTheme(theme) {
  state.theme = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', state.theme);
  localStorage.setItem('theme', state.theme);
}
setTheme(state.theme);

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const text = await res.text();
  let payload;
  try { payload = JSON.parse(text); } catch { payload = text; }
  if (!res.ok) {
    if (typeof payload === 'string') {
      const htmlResponse = /<html|<!doctype/i.test(payload);
      if (htmlResponse) throw new Error(`Ошибка сервера (${res.status}). Повторите позже.`);
      throw new Error(payload || `Ошибка запроса (${res.status})`);
    }
    throw new Error(payload.error || `Ошибка запроса (${res.status})`);
  }
  return payload;
}

async function loadAuthProviders() {
  try {
    state.authProviders = await api('/api/auth/providers');
  } catch {
    state.authProviders = {
      google: { configured: false },
      facebook: { configured: false },
    };
  }
}

function nav(path) {
  const current = location.pathname.replace(/\/$/, '') || '/';
  const target = String(path || '').replace(/\/$/, '') || '/';
  if (current === target) return;
  history.pushState({}, '', path);
  state.notice = null;
  render();
}

function icon(name) {
  const icons = {
    dashboard: '<svg class="icon" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/></svg>',
    create: '<svg class="icon" viewBox="0 0 24 24"><path d="M12 5v14"/><path d="M5 12h14"/></svg>',
    connections: '<svg class="icon" viewBox="0 0 24 24"><path d="M9 15l6-6"/><path d="M7 7h.01"/><path d="M17 17h.01"/><path d="M13 5h4a2 2 0 0 1 2 2v4"/><path d="M11 19H7a2 2 0 0 1-2-2v-4"/></svg>',
    history: '<svg class="icon" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/><path d="M12 7v5l3 3"/></svg>',
    billing: '<svg class="icon" viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="14" rx="3"/><path d="M2 10h20"/><path d="M7 15h4"/></svg>',
    settings: '<svg class="icon" viewBox="0 0 24 24"><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.02.02a2 2 0 0 1-2.83 2.83l-.02-.02A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.56V21a2 2 0 0 1-4 0v-.04A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.02.02a2 2 0 0 1-2.83-2.83l.02-.02A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1H3a2 2 0 0 1 0-4h.04A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.02-.02a2 2 0 0 1 2.83-2.83l.02.02A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.56V3a2 2 0 0 1 4 0v.04A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.87-.34l.02-.02a2 2 0 1 1 2.83 2.83l-.02.02A1.7 1.7 0 0 0 19.4 9c.13.32.46.53.81.53H21a2 2 0 0 1 0 4h-.79c-.35 0-.68.21-.81.53z"/></svg>',
    admin: '<svg class="icon" viewBox="0 0 24 24"><path d="M12 3l8 4v6c0 5-3.5 7.5-8 8-4.5-.5-8-3-8-8V7l8-4z"/><path d="M9.5 12.5l1.7 1.7 3.6-3.6"/></svg>',
    blog: '<svg class="icon" viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
    contact: '<svg class="icon" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  };
  return icons[name] || icons.dashboard;
}

function planBadge(plan) {
  const p = String(plan || 'free').toLowerCase();
  const cls = p === 'pro' ? 'badge-pro' : p === 'agency' ? 'badge-agency' : p === 'light' ? 'badge-light' : 'badge-free';
  return `<span class="badge-plan ${cls}">${esc(p)}</span>`;
}

function statusBadge(status) {
  const key = String(status || '').toLowerCase();
  const map = {
    draft: { cls: 'queued', label: 'Черновик' },
    done: { cls: 'success', label: 'Готово' },
    published: { cls: 'success', label: 'Опубликовано' },
    connected: { cls: 'success', label: 'Подключено' },
    connected_ready: { cls: 'success', label: 'Готово' },
    connected_need_page: { cls: 'warning', label: 'Нужен выбор страницы' },
    not_connected: { cls: 'warning', label: 'Не подключено' },
    token_expired: { cls: 'warning', label: 'Требует переподключения' },
    permissions_missing: { cls: 'warning', label: 'Нужны права' },
    disconnected: { cls: 'error', label: 'Отключено' },
    error: { cls: 'error', label: 'Ошибка' },
    running: { cls: 'warning', label: 'В работе' },
    failed: { cls: 'error', label: 'Ошибка' },
    queued: { cls: 'queued', label: 'В очереди' },
    scheduled: { cls: 'scheduled', label: 'Запланировано' },
  };
  const item = map[key] || { cls: 'warning', label: status || 'неизвестно' };
  return `<span class="status ${item.cls}">${esc(item.label)}</span>`;
}

function isConnectionReady(c) {
  const key = String(c?.status || '').toLowerCase();
  return key === 'connected_ready' || key === 'connected';
}

function field(id, label, type = 'text', value = '', placeholder = '') {
  if (type === 'textarea') return `<div class="field"><label for="${id}">${esc(label)}</label><textarea id="${id}" placeholder="${esc(placeholder)}">${esc(value)}</textarea></div>`;
  return `<div class="field"><label for="${id}">${esc(label)}</label><input id="${id}" type="${esc(type)}" value="${esc(value)}" placeholder="${esc(placeholder)}"/></div>`;
}
function selectField(id, label, value, options) {
  return `<div class="field"><label for="${id}">${esc(label)}</label><select id="${id}">${options.map((o) => `<option value="${esc(o.value)}" ${String(o.value) === String(value) ? 'selected' : ''}>${esc(o.label)}</option>`).join('')}</select></div>`;
}
function progressBar(value, max) {
  const pct = max > 0 ? Math.max(2, Math.min(100, Math.round((value / max) * 100))) : 0;
  return `<div class="progress"><span style="width:${pct}%;"></span></div>`;
}
function emptyState(title, text, buttonLabel, path) {
  return `<div class="empty"><h3>${esc(title)}</h3><p class="small">${esc(text)}</p>${buttonLabel ? `<button class="btn btn-primary" data-link="${esc(path)}">${esc(buttonLabel)}</button>` : ''}</div>`;
}

function appLayout(path, title, body) {
  const links = [
    ['/dashboard', 'РџР°РЅРµР»СЊ', 'dashboard'],
    ['/create', 'РЎРѕР·РґР°С‚СЊ', 'create'],
    ['/connections', 'РџРѕРґРєР»СЋС‡РµРЅРёСЏ', 'connections'],
    ['/history', 'История', 'history'],
    ['/billing', 'РўР°СЂРёС„С‹', 'billing'],
    ['/settings', 'РќР°СЃС‚СЂРѕР№РєРё', 'settings'],
    ['/blog', 'Р‘Р»РѕРі', 'blog'],
    ['/contact', 'РљРѕРЅС‚Р°РєС‚С‹', 'contact'],
  ];
  if (state.user?.role === 'admin') links.push(['/admin', 'РђРґРјРёРЅ', 'admin']);
  const navHtml = links.map(([p, l, i]) => `<button type="button" data-link="${p}" class="nav-link ${path === p ? 'active' : ''}">${icon(i)}<span>${esc(l)}</span></button>`).join('');
  const footer = `<div class="footer-note"><div class="small">Без скрытых платежей. Прозрачные тарифы. Лимиты считаются в постах.</div><div class="small">Stripe защищенные платежи · SSL защищено · GDPR совместимо</div></div>`;
  return `<div class="layout page"><aside class="sidebar"><div class="brand-row"><img class="brand-logo" src="/assets/brand/logo-icon.svg" alt="AutoSocial GPT"/><div><div class="brand-name">AutoSocial GPT</div><div class="small">AI SMM РњРµРЅРµРґР¶РµСЂ</div></div></div>${navHtml}<div class="trust-row" style="margin-top:16px;"><span class="trust-chip">Stripe</span><span class="trust-chip">SSL</span><span class="trust-chip">GDPR</span></div></aside><div><header class="topbar"><div><strong>${esc(title)}</strong><div class="small">${esc(state.user?.email || '')} В· ${planBadge(state.user?.plan || 'free')}</div></div><div class="topbar-actions"><button id="themeToggleBtn" class="btn btn-ghost">${state.theme === 'dark' ? 'РЎРІРµС‚Р»Р°СЏ С‚РµРјР°' : 'РўС‘РјРЅР°СЏ С‚РµРјР°'}</button><button id="logoutBtn" class="btn btn-secondary">Р’С‹Р№С‚Рё</button></div></header><main class="content">${state.notice ? `<div class="notice ${state.notice.type === 'error' ? 'error' : 'ok'}">${esc(state.notice.text)}</div>` : ''}${body}${footer}</main></div></div>`;
}
function pageLogin() {
  const isRegister = state.authMode !== 'login';
  const showSocialLogin = false;
  const formTitle = isRegister ? 'Создать аккаунт' : 'Войти';
  const submitLabel = isRegister ? 'Создать аккаунт' : 'Войти';
  const switchText = isRegister ? 'Уже есть аккаунт?' : 'Нет аккаунта?';
  const switchLabel = isRegister ? 'Войти' : 'Создать';
  const socialBlock = showSocialLogin ? `<div class="social-auth-row"></div>` : '';

  return `<div class="auth-wrap page">
    <div class="auth-shell reveal">
      <section class="auth-panel auth-hero-panel">
        <img src="/assets/brand/logo-full-light.svg" alt="AutoSocial GPT" style="max-width:420px;margin-bottom:18px;"/>

        <div class="hero-block">
          <h1 class="hero__title">AutoSocial GPT — AI-ассистент для управления соцсетями, который делает посты, публикации и стратегии за вас.</h1>
          <p class="hero__subtitle auth-subtitle">Создавайте контент, планируйте публикации и управляйте Facebook + Instagram из одного места — автоматически.</p>
          <div class="cta-row">
            <button id="heroRegisterBtn" class="btn btn-primary cta__button">Начать бесплатно по email</button>
          </div>
          <p class="small hero__microcopy">Без привязки карт сейчас — начните с Free плана.</p>
        </div>

        <div class="features-block">
          <h3>Всё, что нужно для SMM — в одной панели</h3>
          <ul class="auth-benefits">
            <li class="features__item">Генерация уникального контента на основе AI</li>
            <li class="features__item">Автопостинг по расписанию в Facebook и Instagram</li>
            <li class="features__item">Интеллектуальные шаблоны для любых ниш</li>
            <li class="features__item">Планировщик, который думает за вас</li>
            <li class="features__item">Метрики и аналитика для роста</li>
          </ul>
        </div>

        <div class="how-block">
          <h3>Как AutoSocial GPT помогает вашему бизнесу</h3>
          <ul class="check-list">
            <li class="done"><strong>Создавайте контент за секунды</strong><br/><span class="small">Введите тему или ключевое сообщение — получите готовые посты с хештегами и CTA.</span></li>
            <li class="done"><strong>Планируйте. Автоматизируйте. Забывайте о ручной публикации</strong><br/><span class="small">Настройте расписание — и система публикует сама.</span></li>
            <li class="done"><strong>Следите за эффективностью</strong><br/><span class="small">Показы, вовлечённость, рост аудитории — всё в одной панели.</span></li>
          </ul>
        </div>

        <div class="trust-block">
          <h3>Почему маркетологи выбирают AutoSocial GPT</h3>
          <ul class="auth-benefits">
            <li class="features__item">Экономит до 10 часов в неделю на публикациях</li>
            <li class="features__item">Генерирует контент, основанный на бест-практиках SMM</li>
            <li class="features__item">Интеграции с Facebook + Instagram Business</li>
            <li class="features__item">SSL / GDPR-ready. Готово к оплате.</li>
          </ul>
          <blockquote class="auth-quote">“AutoSocial GPT перевёл наши соцсети на автопилот — посты стали чаще, а вовлечённость выросла.” — Маркетолог, SMB</blockquote>
        </div>

        <div class="final-cta-block">
          <h3>Готовы автоматизировать свои соцсети?</h3>
          <div class="cta-row">
            <button id="finalRegisterBtn" class="btn btn-primary cta__button">Создать аккаунт по email</button>
            <button id="finalPricingBtn" class="btn btn-secondary cta__button">Узнать тарифы</button>
          </div>
          <p class="small">Начните с Free плана. Обновление на Pro доступно в любой момент.</p>
        </div>

        <div class="trust-row">
          <span class="trust-chip">SSL</span>
          <span class="trust-chip">GDPR</span>
          <span class="trust-chip">Stripe</span>
        </div>

        <div class="hero-visual auth-hero-visual">
          <img src="/assets/brand/hero-mockup.svg" alt="Интерфейс AutoSocial GPT"/>
        </div>

        <div class="landing-footer-links">
          <button class="btn btn-link" data-link="/billing" type="button">Тарифы</button>
          <a class="btn btn-link" href="https://docs.google.com/document/d/1d7yV-Nxcunz4_DC9VHnCv136o1fnkUidyDhkYFhryPg" target="_blank" rel="noreferrer">Политика конфиденциальности</a>
          <button class="btn btn-link" data-link="/contact" type="button">Поддержка</button>
        </div>
      </section>

      <section class="auth-panel auth-form-panel">
        ${state.notice ? `<div class="notice ${state.notice.type === 'error' ? 'error' : 'ok'}">${esc(state.notice.text)}</div>` : ''}
        <h2>${formTitle}</h2>
        <p class="small mobile-microcopy">Быстрый старт по email и паролю.</p>
        ${socialBlock}
        ${field('authEmail', 'Email', 'email', '', 'you@company.com')}
        ${field('authPassword', 'Пароль', 'password', '', 'Минимум 8 символов')}
        <button id="authSubmitBtn" class="btn btn-primary auth-submit">${submitLabel}</button>
        <div class="auth-switch-row">
          <span class="small">${switchText}</span>
          <button id="authSwitchBtn" class="btn btn-link" type="button">${switchLabel}</button>
        </div>
      </section>
    </div>
  </div>`;
}

function pageDashboard() {
  const b = state.billing || { usage: {}, limits: {}, credits_left: 0, approx_posts_left: 0, plan: 'free' };
  const usedMonth = b.usage.posts_per_month || 0;
  const limitMonth = b.limits.posts_per_month || 0;
  const usedDaily = b.usage.daily_posts || 0;
  const limitDaily = b.limits.daily_posts || 0;
  const hasConnectedAccount = (state.connections || []).some((c) => isConnectionReady(c));
  const latestPosts = (state.posts || []).slice(0, 5);
  // Count only real publishes (scheduled drafts may have remote_id in mock mode).
  const publishedCount = (state.posts || []).filter((p) => !!p.published_at || String(p.status || '').toLowerCase() === 'done').length;
  const hasPublishedPost = publishedCount > 0;
  const onboardingScore = [hasConnectedAccount, state.projects.length > 0, hasPublishedPost].filter(Boolean).length;
  const onboardingPct = Math.round((onboardingScore / 3) * 100);
  const canSchedule = !!b.limits.can_schedule;
  const projectsHtml = state.projects.length
    ? `<div class="grid-2">${state.projects.map((p) => `<article class="card"><div class="row" style="justify-content:space-between;align-items:flex-start;"><div><h3 style="margin-bottom:6px;">${esc(p.name)}</h3><div class="small">Создан: ${new Date(p.created_at).toLocaleDateString()}</div><div class="small">Постов: ${p.posts_count || 0}</div></div><div class="cta-row" style="gap:8px;justify-content:flex-end;"><button class="btn btn-ghost" type="button" data-project-edit="${p.id}" data-project-name="${esc(p.name)}">Переименовать</button></div></div></article>`).join('')}</div>`
    : emptyState('Пока нет проектов', 'Создайте первый проект, чтобы запускать AI-автоматизацию.', 'Создать проект', '/create');
  const recentHtml = latestPosts.length
    ? `<div class="table-wrap"><table><thead><tr><th>Дата</th><th>Платформа</th><th>Тема</th><th>Статус</th></tr></thead><tbody>${latestPosts.map((p) => `<tr><td>${new Date(p.created_at).toLocaleString()}</td><td>${esc(p.platform || '—')}</td><td>${esc(p.topic || '—')}</td><td>${statusBadge(p.status || 'queued')}</td></tr>`).join('')}</tbody></table></div>`
    : `<div class="empty compact"><h3>Пока нет публикаций</h3><p class="small">Сгенерируйте первый пост или запустите AI SMM менеджер.</p><button class="btn btn-primary" data-link="/create">Создать пост</button></div>`;
  const setupChecklist = `<ul class="check-list">
    <li class="${hasConnectedAccount ? 'done' : ''}">1. Подключите Facebook/Instagram</li>
    <li class="${state.projects.length > 0 ? 'done' : ''}">2. Создайте проект</li>
    <li class="${hasPublishedPost ? 'done' : ''}">3. Опубликуйте первый пост</li>
  </ul>`;

  return appLayout('/dashboard', 'Панель', `
    <section class="hero reveal">
      <div class="hero-copy">
        <h1>Ведите соцсети на автопилоте.</h1>
        <p>AutoSocial GPT сам создаёт стратегию, пишет посты и публикует. Вы контролируете только результат.</p>
        <div class="cta-row">
          <button id="goConnectionsBtn" class="btn btn-primary">Подключить Instagram/Facebook</button>
          <button id="goCreateBtn" class="btn btn-secondary">Создать пост</button>
          <button id="goBillingBtn" class="btn btn-ghost">Улучшить тариф</button>
        </div>
      </div>
      <div class="hero-visual"><img src="/assets/brand/hero-mockup.svg" alt="Дашборд"/></div>
    </section>

    <section class="grid-3" style="margin-top:18px;">
      <article class="card">
        <h3>Тариф</h3>
        ${planBadge(b.plan)}
        <p class="small">Кредиты в месяц: ${esc(b.limits.monthly_credits || 0)}</p>
      </article>
      <article class="card">
        <h3>Использовано постов</h3>
        <p class="small">${usedMonth} / ${limitMonth}</p>
        ${progressBar(usedMonth, limitMonth)}
      </article>
      <article class="card">
        <h3>Осталось кредитов</h3>
        <p class="small">${esc(b.credits_left)} кредитов · ~${esc(b.approx_posts_left)} постов</p>
        ${progressBar(Math.max((b.limits.monthly_credits || 1) - (b.credits_left || 0), 0), b.limits.monthly_credits || 1)}
      </article>
    </section>

    <section class="grid-2" style="margin-top:18px;">
      <article class="card">
        <h2>Готовность аккаунта</h2>
        <p class="small">Выполнено ${onboardingScore}/3 шагов · ${onboardingPct}%</p>
        ${progressBar(onboardingScore, 3)}
        <div class="small" style="margin-top:8px;">Опубликовано постов: ${publishedCount}</div>
        ${setupChecklist}
      </article>
      <article class="card">
        <h2>Быстрое создание проекта</h2>
        ${field('dashboardProjectName', 'Название проекта', 'text', '', 'например, Салон Киев')}
        <div class="cta-row">
          <button id="createProjectInlineBtn" class="btn btn-primary">Создать проект</button>
          <button class="btn btn-ghost" data-link="/create">Открыть мастер поста</button>
        </div>
      </article>
    </section>

    <section class="card" style="margin-top:18px;">
      <h2>Запустить AI SMM Менеджер</h2>
      <p class="small">Шаг 1: подключите соцсети. Шаг 2: задайте нишу и цель. Шаг 3: сгенерируйте стратегию на месяц.</p>
      <div class="grid-2">
        <div>
          ${selectField('managerProject', 'Проект', state.projects[0]?.id || '', state.projects.map((p) => ({ value: p.id, label: p.name })).concat([{ value: '', label: 'Проект по умолчанию' }]))}
          ${field('managerBusiness', 'Тип бизнеса', 'text', '', 'например, салон красоты')}
          ${field('managerNiche', 'Ниша', 'text', '', 'например, косметология')}
          ${field('managerGoal', 'Цель', 'text', '', 'например, лиды и записи')}
          ${selectField('managerLang', 'Язык', 'ru', [{ value: 'ru', label: 'Русский' }, { value: 'en', label: 'English' }])}
          <div class="cta-row">
            <button id="startManagerBtn" class="btn btn-primary">Запустить AI SMM Менеджер</button>
            <button id="strategyBtn" class="btn btn-secondary">Сгенерировать стратегию на месяц</button>
          </div>
        </div>
        <div>
          <article class="card" style="height:100%;">
            <h3>Дневной лимит</h3>
            <p class="small">${usedDaily} / ${limitDaily} постов сегодня</p>
            ${progressBar(usedDaily, limitDaily)}
            <h3 style="margin-top:16px;">Быстрые действия</h3>
            <div class="cta-row">
              <button id="postTodayBtn" class="btn btn-ghost">Пост на сегодня</button>
              <button id="scheduleWeekBtn" class="btn btn-ghost" ${canSchedule ? '' : 'disabled'}>План на неделю</button>
            </div>
            ${canSchedule ? '' : '<div class="small" style="margin-top:8px;color:var(--warning);">Планирование доступно на платных тарифах.</div>'}
            <div class="small" style="margin-top:12px;">Статус подключения: ${hasConnectedAccount ? '<span class="status success">подключено</span>' : '<span class="status warning">не подключено</span>'}</div>
          </article>
        </div>
      </div>
    </section>

    <section class="card" style="margin-top:18px;">
      <h2>Последние публикации</h2>
      ${recentHtml}
    </section>

    <section class="card" style="margin-top:18px;">
      <h2>Проекты</h2>
      ${projectsHtml}
    </section>
  `);
}

function pageCreate() {
  const w = state.createWizard;
  const options = state.projects.map((p) => ({ value: p.id, label: p.name }));
  const categoryOptions = [
    { value: 'business', label: 'Бизнес и услуги' },
    { value: 'marketing', label: 'Маркетинг и продвижение' },
    { value: 'fitness', label: 'Фитнес и здоровье' },
    { value: 'ecommerce', label: 'Интернет-магазин' },
    { value: 'beauty', label: 'Красота и уход' },
    { value: 'auto', label: 'Авто и сервис' },
    { value: 'fallback', label: 'Другое' },
  ];
  const categoryHints = {
    business: 'Для экспертов, услуг, локального бизнеса и B2B.',
    marketing: 'Для агентств, SMM, таргета и контент-маркетинга.',
    fitness: 'Для тренеров, залов, wellness и нутрициологии.',
    ecommerce: 'Для карточек товара, акций и прогрева к покупке.',
    beauty: 'Для салонов, косметологии, мастеров красоты.',
    auto: 'Для автосервисов, детейлинга, продажи авто.',
    fallback: 'Универсальный режим, если ниша нестандартная.',
  };
  const topicTemplates = [
    '3 частые ошибки клиентов в выборе услуги',
    'Чек-лист: как подготовиться перед обращением',
    'Кейс: как мы получили результат за 7 дней',
    'Сравнение: 2 подхода и какой выбрать',
    '5 советов, которые экономят бюджет клиенту',
  ];
  const toneOptions = [
    { value: 'friendly', label: 'Дружелюбный', hint: 'Простой и живой язык, без давления.' },
    { value: 'expert', label: 'Экспертный', hint: 'Больше фактов, структуры и пользы.' },
    { value: 'sales', label: 'Продающий', hint: 'Фокус на выгоде и понятном призыве к действию.' },
  ];
  const toneLabel = (toneOptions.find((t) => t.value === w.tone) || toneOptions[0]).label;
  const buildPreviewDraft = () => {
    const topic = (w.topic || '').trim() || 'Польза для клиента';
    return [
      `${topic}: что важно знать перед выбором`,
      '',
      '1) Критерий №1: проверьте опыт и реальные кейсы.',
      '2) Критерий №2: уточните сроки и зону ответственности.',
      '3) Критерий №3: сравните не цену, а итоговую ценность.',
      '',
      'Сохраните пост, чтобы не потерять чек-лист.',
      '#бизнес #маркетинг #продажи',
    ].join('\n');
  };
  const normalizedPreview = (w.previewText || '').trim() || buildPreviewDraft();
  const submitLabel = w.mode === 'schedule' ? 'Создать и запланировать' : (w.mode === 'draft' ? 'Сохранить как черновик' : 'Создать и опубликовать');

  const step1 = `
    ${selectField('wProject', 'Проект', w.projectId, options.length ? options : [{ value: '', label: 'Нет проектов' }])}
    <div class="field">
      <label for="wNewProject">Новый проект</label>
      <div class="cta-row">
        <input id="wNewProject" type="text" placeholder="Например, Салон Киев" />
        <button id="createProjectFromCreateBtn" class="btn btn-secondary" type="button">Добавить проект</button>
      </div>
      <p class="small">Создайте проект прямо здесь, без выхода из мастера.</p>
    </div>`;

  const step2 = `
    <div class="field">
      <label>Платформы</label>
      <div class="row">
        <label><input id="wFb" type="checkbox" ${w.platforms.facebook ? 'checked' : ''}/> Facebook Page</label>
        <label><input id="wIg" type="checkbox" ${w.platforms.instagram ? 'checked' : ''}/> Instagram Business</label>
      </div>
    </div>`;

  const step3 = `
    <article class="wizard-help">
      <h3>Что заполнить на этом шаге</h3>
      <p class="small">1) Выберите категорию бизнеса. 2) Введите тему поста. 3) Выберите стиль текста (тон).</p>
    </article>
    ${selectField('wCategory', 'Категория бизнеса', w.category, categoryOptions)}
    <p class="small wizard-inline-help">${esc(categoryHints[w.category] || categoryHints.business)}</p>
    ${field('wTopic', 'Тема поста', 'text', w.topic, 'Например: 3 ошибки при выборе автосервиса')}
    <div class="field">
      <label>Быстрые темы</label>
      <div class="topic-template-row">
        ${topicTemplates.map((t) => `<button type="button" class="btn btn-ghost btn-topic-template" data-topic-template="${esc(t)}">${esc(t)}</button>`).join('')}
      </div>
    </div>
    ${selectField('wTone', 'Тон текста', w.tone, toneOptions.map((t) => ({ value: t.value, label: t.label })))}
    <p class="small wizard-inline-help">${esc((toneOptions.find((t) => t.value === w.tone) || toneOptions[0]).hint)}</p>
    ${selectField('wLang', 'Язык', w.language, [{ value: 'ru', label: 'Русский' }, { value: 'en', label: 'English' }])}
    ${field('wMedia', 'Ссылка на изображение (необязательно)', 'text', w.mediaUrl, 'https://...')}`;

  const step4 = `
    <article class="wizard-help">
      <h3>Предпросмотр перед публикацией</h3>
      <p class="small">Проверьте и отредактируйте текст. Этот вариант отправится в публикацию.</p>
    </article>
    <div class="wizard-summary">
      <span class="pill">Категория: ${esc((categoryOptions.find((c) => c.value === w.category) || categoryOptions[0]).label)}</span>
      <span class="pill">Тон: ${esc(toneLabel)}</span>
      <span class="pill">Язык: ${esc(w.language === 'ru' ? 'Русский' : 'English')}</span>
    </div>
    ${field('wPreviewText', 'Текст поста (можно редактировать)', 'textarea', normalizedPreview, 'Введите текст публикации')}
    <p class="small wizard-inline-help">Рекомендуем: 500-1200 символов, 3-5 хештегов, 1 чёткий призыв к действию.</p>
  `;

  const step5 = `
    ${selectField('wMode', 'Режим публикации', w.mode, [{ value: 'now', label: 'Опубликовать сейчас' }, { value: 'schedule', label: 'Запланировать на дату' }, { value: 'draft', label: 'Сохранить как черновик' }])}
    ${w.mode === 'schedule' ? field('wSchedule', 'Дата и время публикации', 'datetime-local', w.scheduleAt) : ''}
    <article class="wizard-help">
      <h3>Итог перед запуском</h3>
      <p class="small">Проект: <strong>${esc((state.projects.find((p) => String(p.id) === String(w.projectId)) || state.projects[0] || { name: 'Не выбран' }).name)}</strong> · Платформы: <strong>${esc([w.platforms.facebook ? 'Facebook' : null, w.platforms.instagram ? 'Instagram' : null].filter(Boolean).join(' + ') || 'Не выбрано')}</strong></p>
      <p class="small">Тема: <strong>${esc(w.topic || '—')}</strong></p>
    </article>
    <p class="small">Планирование доступно на платных тарифах. В режиме черновика пост не публикуется.</p>
  `;

  const stepContent = [step1, step2, step3, step4, step5][w.step - 1] || step1;
  return appLayout('/create', 'Создать', `<section class="card"><h2>Мастер создания поста</h2><div class="stepper"><div class="step ${w.step===1?'active':''}">1. Проект</div><div class="step ${w.step===2?'active':''}">2. Платформы</div><div class="step ${w.step===3?'active':''}">3. Контент</div><div class="step ${w.step===4?'active':''}">4. Предпросмотр</div><div class="step ${w.step===5?'active':''}">5. Публикация</div></div>${stepContent}<div class="cta-row" style="margin-top:10px;">${w.step>1?'<button id="wPrev" class="btn btn-ghost">Назад</button>':''}${w.step<5?'<button id="wNext" class="btn btn-primary">Далее</button>':`<button id="wSubmit" class="btn btn-primary">${esc(submitLabel)}</button>`}</div></section>`);
}
function pageConnections() {
  const query = new URLSearchParams(location.search);
  const err = query.get('error');
  const msg = query.get('message');
  if (err) {
    const map = {
      oauth_denied: 'Вы отменили подключение Facebook.',
      token_exchange_failed: 'Не удалось обменять код на токен. Проверьте App ID/Secret и Redirect URI.',
      state_invalid: 'Сессия OAuth устарела. Запустите подключение заново.',
      meta_api_error: 'Meta API вернул ошибку при получении страниц/Instagram.',
      no_pages: 'У этого Facebook-аккаунта нет доступных страниц для подключения.',
      no_ig_business: 'На выбранной странице нет Instagram Business, привязанного к странице.',
    };
    state.notice = { type: 'error', text: (map[err] || 'Ошибка подключения.') + (msg ? ` ${msg}` : '') };
  } else if (query.get('connected')) {
    state.notice = { type: 'ok', text: 'Facebook/Instagram аккаунт подключён.' };
  }

  const primaryByStatus = (status) => {
    const s = String(status || '').toLowerCase();
    if (s === 'not_connected') return { action: 'connect', label: 'Подключить Facebook' };
    if (s === 'connected_need_page') return { action: 'pick_page', label: 'Выбрать страницу' };
    if (s === 'connected_ready' || s === 'connected') return { action: 'test', label: 'Тест публикации' };
    if (s === 'token_expired' || s === 'permissions_missing' || s === 'disconnected') return { action: 'reconnect', label: 'Переподключить' };
    return { action: 'retry', label: 'Повторить' };
  };

  const cards = state.connections.length
    ? `<div class="grid-2">${state.connections.map((c) => {
        const status = String(c.status || 'not_connected').toLowerCase();
        const primary = primaryByStatus(status);
        const avatar = c.facebook_page_picture_url
          ? `<span class="avatar"><img src="${esc(c.facebook_page_picture_url)}" alt="" /></span>`
          : `<span class="avatar">${esc((safeText(c.facebook_page_name, 'P')[0] || 'P').toUpperCase())}</span>`;
        const pageLine = c.facebook_page_name
          ? `${esc(c.facebook_page_name)} <span class="small">(${esc(safeText(c.facebook_page_id))})</span>`
          : `<span class="small">Страница не выбрана</span>`;
        const igLine = c.instagram_business_id
          ? `${esc(safeText(c.instagram_username, '')) ? `@${esc(c.instagram_username)} ` : ''}<span class="small">(${esc(c.instagram_business_id)})</span>`
          : `<span class="small">Instagram Business не выбран</span>`;
        const createdAt = c.created_at ? new Date(c.created_at).toLocaleString() : '—';
        const updatedAt = c.updated_at ? new Date(c.updated_at).toLocaleString() : '—';
        const lastSuccessAt = c.last_success_at ? new Date(c.last_success_at).toLocaleString() : '—';
        const expAt = c.token_expires_at ? new Date(c.token_expires_at).toLocaleString() : 'неизвестно';
        const howToFix = c.status_help_text || 'Проверьте детали подключения.';
        const canRefresh = status === 'connected_ready' || status === 'connected' || status === 'token_expired';
        const isError = status === 'error';
        return `<article class="card">
          <div class="row" style="justify-content:space-between;align-items:flex-start;">
            <div>
              <div class="row" style="align-items:center;gap:10px;"><span class="pill">Meta</span></div>
              <div class="row" style="align-items:center;gap:12px;margin-top:10px;">${avatar}<h3 style="margin:0;">Facebook + Instagram</h3></div>
              <div class="small" style="margin-top:6px;">Подключение для автопостинга. Токены не показываем.</div>
            </div>
            <div>${statusBadge(status)}</div>
          </div>

          <div class="grid-2" style="margin-top:14px;">
            <div><div class="pill">Facebook Page</div><div style="font-weight:900;margin-top:6px;">${pageLine}</div></div>
            <div><div class="pill">Instagram Business</div><div style="font-weight:900;margin-top:6px;">${igLine}</div></div>
          </div>

          <div class="small" style="margin-top:10px;">${esc(howToFix)}</div>

          <div class="cta-row" style="margin-top:12px;">
            <button class="btn btn-primary" data-primary-action="${esc(primary.action)}" data-connection-id="${c.id}">${esc(primary.label)}</button>
            ${canRefresh ? `<button class="btn btn-secondary" data-refresh="${c.id}">Обновить токен</button>` : ''}
            ${isError ? `<button class="btn btn-secondary" data-open-details="${c.id}">Детали</button>` : ''}
            <button class="btn btn-danger" data-disconnect="${c.id}">Отключить</button>
          </div>

          <details style="margin-top:10px;">
            <summary class="small" style="cursor:pointer;">Детали</summary>
            <div class="small" style="margin-top:8px;">
              <div><strong>Connection ID:</strong> ${esc(c.id)}</div>
              <div><strong>Статус:</strong> ${esc(status)}</div>
              <div data-testid="meta-reason-code"><strong>Код причины:</strong> ${esc(safeText(c.status_reason_code, '—'))}</div>
              <div data-testid="meta-redirect-uri"><strong>META_REDIRECT_URI:</strong> ${esc(safeText(c.meta_redirect_uri, '—'))}</div>
              <div><strong>Page ID:</strong> ${esc(safeText(c.facebook_page_id))}</div>
              <div><strong>Page picture:</strong> ${esc(safeText(c.facebook_page_picture_url, '—'))}</div>
              <div><strong>IG User ID:</strong> ${esc(safeText(c.instagram_business_id))}</div>
              <div><strong>IG Username:</strong> ${esc(safeText(c.instagram_username))}</div>
              <div><strong>Создано:</strong> ${esc(createdAt)}</div>
              <div><strong>Обновлено:</strong> ${esc(updatedAt)}</div>
              <div><strong>Последний успех:</strong> ${esc(lastSuccessAt)}</div>
              <div><strong>Токен истекает:</strong> ${esc(expAt)}</div>
              <div class="small" style="margin-top:8px;"><strong>Что делать:</strong> ${esc(howToFix)}</div>
              <div class="cta-row" style="margin-top:8px;"><button class="btn btn-ghost" data-copy-tech="${esc(c.id)}">Скопировать тех.лог</button></div>
            </div>
          </details>
        </article>`;
      }).join('')}</div>`
    : emptyState('Нет подключенных аккаунтов', 'Подключите Facebook Page и Instagram Business, чтобы начать публикацию.', 'Подключить Facebook', '/connections');

  const picker = state.connectionPicker || { open: false, loading: false, pages: [], selectedPageId: '', error: '' };
  const pageMatches = (p) => {
    const q = String(picker.query || '').trim().toLowerCase();
    if (!q) return true;
    return String(p.page_name || '').toLowerCase().includes(q) || String(p.page_id || '').includes(q) || String(p.ig_username || '').toLowerCase().includes(q);
  };
  const pageInFilter = (p) => {
    if (picker.filter === 'with_ig') return !!p.has_ig;
    if (picker.filter === 'without_ig') return !p.has_ig;
    return true;
  };
  const visiblePages = (picker.pages || []).filter((p) => pageInFilter(p) && pageMatches(p));

  const pickerList = picker.loading
    ? `<p class="small">Загружаю список страниц…</p>`
    : (picker.error
        ? `<p class="small" style="color:var(--error);">${esc(picker.error)}</p>`
        : (picker.pages.length
            ? `<div class="list">${visiblePages.map((p) => {
                const pic = p.page_picture_url ? `<span class="avatar"><img src="${esc(p.page_picture_url)}" alt="" /></span>` : `<span class="avatar">${esc((safeText(p.page_name,'P')[0] || 'P').toUpperCase())}</span>`;
                const ig = p.has_ig ? `<span class="pill ok">IG привязан</span>` : `<span class="pill warn">Без IG</span>`;
                const checked = String(picker.selectedPageId) === String(p.page_id) ? 'checked' : '';
                const already = p.already_connected ? `<span class="pill">уже добавлена</span>` : '';
                return `<label class="list-item"><div><div class="row" style="align-items:center;gap:10px;">${pic}<div><div style="font-weight:800;">${esc(safeText(p.page_name))}</div><div class="meta">Page ID: ${esc(safeText(p.page_id))}${p.ig_user_id ? ` • IG: ${esc(safeText(p.ig_user_id))}` : ''}${p.ig_username ? ` (@${esc(p.ig_username)})` : ''}</div></div></div></div><div class="row" style="align-items:center;gap:10px;">${already}${ig}<input type="radio" name="pagePick" value="${esc(p.page_id)}" ${checked} /></div></label>`;
              }).join('')}</div>`
            : `<p class="small">Страницы не найдены. Проверьте, что у аккаунта есть роль на Facebook Page и выданы permissions (pages_show_list).</p>`));

  const modal = `<div id="connectionPickerBackdrop" class="modal-backdrop ${picker.open ? 'open' : ''}"><div class="modal" role="dialog" aria-modal="true"><div class="modal-header"><h3>Выбор Facebook Page</h3><button id="closePickerBtn" class="btn btn-ghost">Закрыть</button></div><div class="modal-body"><p class="small">Покажем все страницы, к которым у вашего токена есть доступ. Выберите нужную для публикаций.</p><div class="row" style="justify-content:space-between;align-items:center;margin:10px 0;"><div class="cta-row"><button id="filterAllBtn" class="btn btn-ghost">Все</button><button id="filterWithIgBtn" class="btn btn-ghost">С IG</button><button id="filterWithoutIgBtn" class="btn btn-ghost">Без IG</button></div><input id="pageSearchInput" style="max-width:320px;" placeholder="Поиск: название / Page ID / @IG" /></div>${pickerList}</div><div class="cta-row" style="margin-top:12px;justify-content:flex-end;"><button id="refreshPagesBtn" class="btn btn-secondary">Обновить список</button><button id="savePickedPageBtn" class="btn btn-primary" ${picker.selectedPageId ? '' : 'disabled'}>Использовать</button><button id="addPickedPageBtn" class="btn btn-secondary" ${picker.selectedPageId ? '' : 'disabled'}>Добавить как отдельное</button></div></div></div>`;

  return appLayout('/connections', 'Подключения', `<section class="card"><h2>Подключенные аккаунты</h2><p class="small">Подключите один раз и публикуйте автоматически. Если страниц несколько, выберите нужную.</p><div class="cta-row" style="margin-bottom:12px;"><button id="connectMetaBtn" data-testid="connect-meta-btn" class="btn btn-primary">Подключить Facebook</button><button id="connectDemoBtn" class="btn btn-secondary">Подключить demo-аккаунт</button></div>${cards}</section>${modal}`);
}

function plansTable() {
  const planMap = {};
  (state.plans || []).forEach((p) => { planMap[p.name] = p; });
  const f = (name, key, fallback = '-') => planMap[name]?.[key] ?? fallback;
  const yesNo = (v) => (v ? 'Да' : 'Нет');
  const price = (name) => {
    const v = planMap[name]?.price_eur_month;
    if (v === undefined || v === null) return '—';
    const n = Number(v) || 0;
    return n <= 0 ? '€0' : `€${n}`;
  };
  const projects = (name) => {
    const v = planMap[name]?.max_projects;
    if (String(name) === 'agency') return 'Без ограничений';
    return v ?? '—';
  };
  const templates = (name) => yesNo(!!planMap[name]?.templates_enabled);
  const team = (name) => {
    const v = planMap[name]?.team_seats;
    return v ? `${v}` : '—';
  };
  return `<div class="table-wrap"><table class="pricing-table"><thead><tr><th>Функция</th><th>Free</th><th>Light</th><th>Pro</th><th>Agency</th></tr></thead><tbody>
    <tr><td>Цена / месяц</td><td>${price('free')}</td><td>${price('light')}</td><td>${price('pro')}</td><td>${price('agency')}</td></tr>
    <tr><td>Постов / месяц</td><td>${f('free','max_posts_month',10)}</td><td>${f('light','max_posts_month',300)}</td><td>${f('pro','max_posts_month',1000)}</td><td>${f('agency','max_posts_month',5000)}</td></tr>
    <tr><td>Проекты</td><td>${projects('free')}</td><td>${projects('light')}</td><td>${projects('pro')}</td><td>${projects('agency')}</td></tr>
    <tr><td>Планирование</td><td>${yesNo(f('free','can_schedule',false))}</td><td>${yesNo(f('light','can_schedule',true))}</td><td>${yesNo(f('pro','can_schedule',true))}</td><td>${yesNo(f('agency','can_schedule',true))}</td></tr>
    <tr><td>Автопубликация</td><td>${yesNo(f('free','can_autopublish',false))}</td><td>${yesNo(f('light','can_autopublish',true))}</td><td>${yesNo(f('pro','can_autopublish',true))}</td><td>${yesNo(f('agency','can_autopublish',true))}</td></tr>
    <tr><td>Шаблоны</td><td>${templates('free')}</td><td>${templates('light')}</td><td>${templates('pro')}</td><td>${templates('agency')}</td></tr>
    <tr><td>Команда</td><td>—</td><td>—</td><td>—</td><td>${team('agency')}</td></tr>
  </tbody></table></div>`;
}

function pricingCards() {
  const planMap = {};
  (state.plans || []).forEach((p) => { planMap[p.name] = p; });

  const current = String(state.user?.plan || 'free').toLowerCase();
  const order = ['free', 'light', 'pro', 'agency'];
  const meta = {
    free: { title: 'Free', desc: 'Для теста: подключили соцсети, сделали первые посты.' },
    light: { title: 'Light', desc: 'Для малого бизнеса: регулярные посты и планирование.' },
    pro: { title: 'Pro', desc: 'Для тех, кто хочет автопостинг и стабильный поток контента.', highlight: true },
    agency: { title: 'Agency', desc: 'Для агентств и команд: много проектов и лимитов.' },
  };
  const price = (name) => {
    const v = planMap[name]?.price_eur_month;
    const n = Number(v) || 0;
    return n <= 0 ? '€0' : `€${n}`;
  };
  const projects = (name) => (name === 'agency' ? 'Без ограничений' : (planMap[name]?.max_projects ?? '—'));
  const posts = (name) => (planMap[name]?.max_posts_month ?? '—');
  const daily = (name) => (planMap[name]?.max_daily_posts ?? '—');
  const yesNo = (v) => (v ? 'Да' : 'Нет');

  return `<div class="pricing-grid">
    ${order.map((name) => {
      const m = meta[name] || { title: name, desc: '' };
      const isCurrent = current === name;
      const canUpgrade = name !== 'free';
      const btn = isCurrent
        ? `<button class="btn btn-secondary" disabled>Текущий тариф</button>`
        : canUpgrade
          ? `<button class="btn ${m.highlight ? 'btn-primary' : 'btn-secondary'}" data-upgrade="${esc(name)}">Перейти на ${esc(m.title)}</button>`
          : `<button class="btn btn-ghost" disabled>Бесплатно</button>`;
      return `<article class="card plan-card ${m.highlight ? 'highlight' : ''}">
        <div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;">
          <div>
            <div class="plan-title">${esc(m.title)}</div>
            <div class="plan-price">${price(name)}<span class="plan-price-suffix">/мес</span></div>
            <div class="small muted" style="margin-top:6px;">${esc(m.desc)}</div>
          </div>
          <div>${planBadge(name)}</div>
        </div>
        <div class="plan-features">
          <div class="small"><strong>${posts(name)}</strong> постов/мес</div>
          <div class="small"><strong>${projects(name)}</strong> проектов</div>
          <div class="small"><strong>${daily(name)}</strong> постов/день</div>
          <div class="small">Планирование: <strong>${yesNo(!!planMap[name]?.can_schedule)}</strong></div>
          <div class="small">Автопостинг: <strong>${yesNo(!!planMap[name]?.can_autopublish)}</strong></div>
        </div>
        <div class="cta-row" style="margin-top:12px;justify-content:space-between;gap:10px;">
          ${btn}
          ${m.highlight ? `<span class="hint-pill">Рекомендуем</span>` : `<span></span>`}
        </div>
      </article>`;
    }).join('')}
  </div>`;
}

function pageHistory() {
  const viewer = state.postViewer || { open: false, loading: false, post: null, error: '' };
  const editor = state.postEditor || { open: false, saving: false, post: null, error: '' };
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dayMs = 24 * 60 * 60 * 1000;
  const dayKeys = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start.getTime() + i * dayMs);
    return d.toISOString().slice(0, 10);
  });
  const dateToKey = (value) => {
    if (!value) return '';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '';
    const local = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    return local.toISOString().slice(0, 10);
  };
  const toLocalInput = (value) => {
    if (!value) return '';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const plannerStatus = (p) => ((p.published_at || String(p.status || '').toLowerCase() === 'done') ? 'published' : 'draft');
  const plannerColumns = [{ key: 'draft', label: 'Черновики' }, ...dayKeys.map((k) => {
    const d = new Date(`${k}T00:00:00`);
    return { key: k, label: d.toLocaleDateString('ru-RU', { weekday: 'short', day: '2-digit', month: '2-digit' }) };
  })];
  const grouped = Object.fromEntries(plannerColumns.map((c) => [c.key, []]));
  for (const p of (state.posts || [])) {
    const published = plannerStatus(p) === 'published';
    const calendarDate = published ? (p.published_at || p.schedule_at) : p.schedule_at;
    const calendarKey = dateToKey(calendarDate);
    const key = calendarKey && dayKeys.includes(calendarKey) ? calendarKey : 'draft';
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(p);
  }
  for (const key of Object.keys(grouped)) {
    grouped[key].sort((a, b) => {
      const da = new Date(a.published_at || a.schedule_at || a.created_at).getTime();
      const db = new Date(b.published_at || b.schedule_at || b.created_at).getTime();
      return da - db;
    });
  }

  const plannerBoard = `<section class="card planner-card">
    <div class="row" style="justify-content:space-between;align-items:center;">
      <h3 style="margin:0;">Календарь публикаций</h3>
      <div class="small">Перетаскивайте посты по дням. В “Черновики” — без расписания.</div>
    </div>
    <div class="planner-grid">
      ${plannerColumns.map((col) => {
        const cards = (grouped[col.key] || []).map((p) => {
          const status = plannerStatus(p);
          const canDrag = status !== 'published';
          const title = p.topic || p.title_preview || `Пост #${p.id}`;
          return `<article class="planner-post ${canDrag ? '' : 'locked'}"
              draggable="${canDrag ? 'true' : 'false'}"
              data-post-card="${p.id}">
              <div class="row" style="justify-content:space-between;align-items:flex-start;">
                <strong class="truncate" title="${esc(title)}">${esc(title)}</strong>
                ${statusBadge(status)}
              </div>
              <div class="small">${esc(p.platform || '—')}</div>
              <div class="small">${p.published_at ? `Опубликовано: ${esc(new Date(p.published_at).toLocaleString())}` : (p.schedule_at ? `План: ${esc(new Date(p.schedule_at).toLocaleString())}` : 'Без даты')}</div>
              <div class="cta-row" style="margin-top:8px;">
                <button class="btn btn-ghost" data-edit-post="${p.id}">Редактировать</button>
                ${status === 'published' ? '' : `<button class="btn btn-secondary" data-publish-now="${p.id}">Опубликовать</button>`}
              </div>
            </article>`;
        }).join('');
        return `<div class="planner-column" data-drop-col="${col.key}">
          <div class="planner-column-head">${esc(col.label)}</div>
          <div class="planner-column-body">
            ${cards || `<div class="small muted planner-empty">Нет постов</div>`}
          </div>
        </div>`;
      }).join('')}
    </div>
  </section>`;

  const table = state.posts.length
    ? `<div class="table-wrap"><table>
        <thead><tr>
          <th>Дата</th>
          <th>Платформа</th>
          <th>Тема</th>
          <th>Статус</th>
          <th>Публикация</th>
          <th>Действия</th>
        </tr></thead>
        <tbody>
          ${state.posts.map((p) => {
            const pub = p.published_at ? `Опубликовано: ${new Date(p.published_at).toLocaleString()}` : (p.schedule_at ? `Запланировано: ${new Date(p.schedule_at).toLocaleString()}` : '—');
            const retryDisabled = (p.status === 'queued' || p.status === 'running') ? 'disabled' : '';
            const title = ((p.topic || '').trim() && (p.topic || '').includes('?') && (p.title_preview || '').trim())
              ? p.title_preview
              : (p.topic || p.title_preview || '—');
            const publishDisabled = (p.status === 'done' || p.status === 'failed') ? 'disabled' : '';
            return `<tr>
              <td>${new Date(p.created_at).toLocaleString()}</td>
              <td>${esc(p.platform)}</td>
              <td class="truncate" title="${esc(title)}">${esc(title)}</td>
              <td>${statusBadge(plannerStatus(p))}</td>
              <td class="small">${esc(pub)}</td>
              <td>
                <div class="cta-row" style="justify-content:flex-end;">
                  <button class="btn btn-ghost" data-edit-post="${p.id}">Редактировать</button>
                  <button class="btn btn-secondary" data-publish-now="${p.id}" ${publishDisabled}>Опубликовать</button>
                  <button class="btn btn-ghost" data-view-post="${p.id}">Открыть</button>
                  <button class="btn btn-ghost" data-retry="${p.id}" ${retryDisabled}>Повтор</button>
                </div>
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table></div>`
    : emptyState('История пуста', 'Создайте первый пост и опубликуйте его.', 'Создать пост', '/create');

  const modalBody = viewer.loading
    ? `<p class="small">Загружаю пост…</p>`
    : (viewer.error
        ? `<p class="small" style="color:var(--error);">${esc(viewer.error)}</p>`
        : (viewer.post
            ? (() => {
                const p = viewer.post;
                const meta = [
                  p.platform ? `Платформа: <strong>${esc(p.platform)}</strong>` : '',
                  p.status ? `Статус: ${statusBadge(p.status)}` : '',
                  p.schedule_at ? `План: <strong>${esc(new Date(p.schedule_at).toLocaleString())}</strong>` : '',
                  p.published_at ? `Публикация: <strong>${esc(new Date(p.published_at).toLocaleString())}</strong>` : '',
                ].filter(Boolean).join(' • ');
                const text = (p.generated_text || '').trim();
                const body = text
                  ? `<div class="post-preview" style="white-space:pre-wrap;line-height:1.45;">${esc(text)}</div>`
                  : `<p class="small muted">Текст еще не готов. Если статус “queued/running”, подождите 10–30 секунд и откройте снова.</p>`;
                const err = p.error_message ? `<p class="small" style="color:var(--error);margin-top:10px;">Ошибка: ${esc(p.error_message)}</p>` : '';
                const prompt = (p.prompt_text || '').trim();
                const details = prompt ? `<details style="margin-top:12px;"><summary class="small">Промпт (для диагностики)</summary><pre class="small" style="white-space:pre-wrap;margin-top:10px;">${esc(prompt)}</pre></details>` : '';
                return `<div>
                  <div class="small muted">${meta || ''}</div>
                  <h3 style="margin-top:10px;">${esc(p.topic || 'Пост')}</h3>
                  ${body}
                  ${err}
                  ${details}
                </div>`;
              })()
            : `<p class="small muted">Выберите пост в таблице.</p>`));

  const modal = `<div id="postViewerBackdrop" class="modal-backdrop ${viewer.open ? 'open' : ''}">
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-header">
        <h3>Пост</h3>
        <button id="closePostViewerBtn" class="btn btn-ghost">Закрыть</button>
      </div>
      <div class="modal-body">
        ${modalBody}
      </div>
    </div>
  </div>`;

  const editorBody = editor.post ? `<div>
    ${editor.error ? `<p class="small" style="color:var(--error);">${esc(editor.error)}</p>` : ''}
    ${field('editTopic', 'Тема', 'text', editor.post.topic || '')}
    ${field('editText', 'Текст', 'textarea', editor.post.generated_text || '')}
    ${selectField('editPlatform', 'Платформа', editor.post.platform || 'instagram', [
      { value: 'instagram', label: 'Instagram' },
      { value: 'facebook', label: 'Facebook' },
    ])}
    ${field('editMedia', 'Ссылка на изображение (опц.)', 'text', editor.post.media_url || '', 'https://...')}
    ${field('editSchedule', 'Дата и время публикации (опц.)', 'datetime-local', toLocalInput(editor.post.schedule_at))}
    <div class="cta-row" style="justify-content:flex-end;margin-top:12px;">
      <button id="clearScheduleBtn" class="btn btn-ghost" ${editor.saving ? 'disabled' : ''}>Снять с расписания</button>
      <button id="savePostEditBtn" class="btn btn-primary" ${editor.saving ? 'disabled' : ''}>${editor.saving ? 'Сохраняю…' : 'Сохранить'}</button>
    </div>
  </div>` : `<p class="small muted">Пост не выбран.</p>`;

  const editModal = `<div id="postEditBackdrop" class="modal-backdrop ${editor.open ? 'open' : ''}">
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-header">
        <h3>Редактирование перед публикацией</h3>
        <button id="closePostEditBtn" class="btn btn-ghost">Закрыть</button>
      </div>
      <div class="modal-body">${editorBody}</div>
    </div>
  </div>`;

  return appLayout('/history','История',`${plannerBoard}<section class="card"><h2>История публикаций</h2>${table}</section>${modal}${editModal}`);
}

function pageBilling() {
  const b = state.billing || { plan: 'free', usage: {}, limits: {} };
  const usedMonth = b.usage.posts_per_month || 0;
  const limitMonth = b.limits.posts_per_month || 0;
  const usedDaily = b.usage.daily_posts || 0;
  const limitDaily = b.limits.daily_posts || 0;

  const billingInfo = `<section class="grid-2" style="margin-bottom:18px;">
    <article class="card">
      <h2 style="margin-bottom:6px;">Тарифы и биллинг</h2>
      <p class="small">Платите за автопостинг и удобство. Лимиты отображаются в постах.</p>
      <p class="small muted" style="margin-top:8px;">Важно: у Instagram есть лимит публикаций через API на один IG Business (обычно до ~100 за 24 часа). Если подключений несколько, система распределяет нагрузку.</p>
      <div class="cta-row" style="margin-top:12px;">
        <button class="btn btn-ghost" data-portal="1">Управление подпиской</button>
      </div>
    </article>
    <article class="card">
      <h3>Использование</h3>
      <div class="small">Постов в месяц: <strong>${usedMonth}</strong> / <strong>${limitMonth || '—'}</strong></div>
      ${progressBar(usedMonth, limitMonth || 0)}
      <div class="small" style="margin-top:10px;">Лимит на день: <strong>${usedDaily}</strong> / <strong>${limitDaily || '—'}</strong></div>
      ${progressBar(usedDaily, limitDaily || 0)}
    </article>
  </section>`;

  return appLayout(
    '/billing',
    'Тарифы',
    `${billingInfo}
     ${pricingCards()}
     <section class="card" style="margin-top:18px;">
       <h3>Сравнение тарифов</h3>
       ${plansTable()}
       <div class="small muted" style="margin-top:10px;">Если Stripe не настроен локально, кнопки оплаты покажут понятную ошибку. Для теста можно оставить Free.</div>
     </section>`
  );
}

function pageSettings() {
  return appLayout('/settings','РќР°СЃС‚СЂРѕР№РєРё',`<section class="grid-2"><article class="card"><h2>РџСЂРѕС„РёР»СЊ</h2>${field('profileEmail','Email','text',state.user?.email || '')}<button id="saveProfileBtn" class="btn btn-primary">РЎРѕС…СЂР°РЅРёС‚СЊ РїСЂРѕС„РёР»СЊ</button></article><article class="card"><h2>РџР°СЂРѕР»СЊ</h2>${field('curPass','РўРµРєСѓС‰РёР№ РїР°СЂРѕР»СЊ','password')}${field('newPass','РќРѕРІС‹Р№ РїР°СЂРѕР»СЊ','password')}<button id="savePassBtn" class="btn btn-secondary">РћР±РЅРѕРІРёС‚СЊ РїР°СЂРѕР»СЊ</button></article></section>`);
}

function pageBlog() {
  const items = state.blog.length ? `<div class="grid-2">${state.blog.map((b)=>`<article class="card"><h3>${esc(b.title)}</h3><div class="small">${new Date(b.published_at).toLocaleDateString()}</div><p class="small">${esc((b.meta_description || '').slice(0,220))}</p></article>`).join('')}</div>` : emptyState('Р‘Р»РѕРі РїРѕРєР° РїСѓСЃС‚','Р•Р¶РµРґРЅРµРІРЅС‹Рµ SEO-СЃС‚Р°С‚СЊРё Р±СѓРґСѓС‚ РїРѕСЏРІР»СЏС‚СЊСЃСЏ Р·РґРµСЃСЊ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё.','','');
  return appLayout('/blog','Р‘Р»РѕРі',`<section class="card"><h2>SEO Р±Р»РѕРі-РґРІРёР¶РѕРє</h2>${items}</section>`);
}

function pageContact() {
  return appLayout('/contact','РљРѕРЅС‚Р°РєС‚С‹',`<section class="grid-2"><article class="card"><h2>РљРѕРЅС‚Р°РєС‚С‹</h2><p class="small">РќСѓР¶РЅР° РїРѕРјРѕС‰СЊ СЃ РѕРЅР±РѕСЂРґРёРЅРіРѕРј, РЅР°СЃС‚СЂРѕР№РєРѕР№ Meta РёР»Рё Р±РёР»Р»РёРЅРіРѕРј?</p><p><strong>Email:</strong> support@autosocial-gpt.local</p><p><strong>РљРѕРјРїР°РЅРёСЏ:</strong> AutoSocial GPT SaaS</p><p><strong>Р’СЂРµРјСЏ СЂР°Р±РѕС‚С‹:</strong> РџРЅ-РџС‚ 09:00-18:00 UTC</p></article><article class="card"><h2>Р‘РµР·РѕРїР°СЃРЅРѕСЃС‚СЊ Рё СЃРѕРѕС‚РІРµС‚СЃС‚РІРёРµ</h2><ul class="small"><li>Р‘РµР·РѕРїР°СЃРЅС‹Рµ РїР»Р°С‚РµР¶Рё Stripe</li><li>SSL-С€РёС„СЂРѕРІР°РЅРёРµ СЃРѕРµРґРёРЅРµРЅРёР№</li><li>РЎРѕРѕС‚РІРµС‚СЃС‚РІРёРµ GDPR</li><li>Р‘РµР· СЃРєСЂС‹С‚С‹С… РїР»Р°С‚РµР¶РµР№</li></ul></article></section>`);
}

function adminUsersTable() {
  if (!state.adminUsers.length) return '<p class="small">Р—Р°РіСЂСѓР·РёС‚Рµ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ РґР»СЏ РїСЂРѕСЃРјРѕС‚СЂР°.</p>';
  return `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Email</th><th>Р РѕР»СЊ</th><th>РўР°СЂРёС„</th><th>РљСЂРµРґРёС‚С‹</th><th>Р‘РёР»Р»РёРЅРі</th><th>РЎРѕР·РґР°РЅ</th></tr></thead><tbody>${state.adminUsers.map((u)=>`<tr><td>${u.id}</td><td>${esc(u.email)}</td><td>${esc(u.role)}</td><td>${planBadge(u.plan)}</td><td>${u.credits_left}</td><td>${esc(u.billing_status || 'вЂ”')}</td><td>${new Date(u.created_at).toLocaleDateString()}</td></tr>`).join('')}</tbody></table></div>`;
}

function pageAdmin() {
  if (state.user?.role !== 'admin') return appLayout('/admin','РђРґРјРёРЅ',emptyState('Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰РµРЅ','РўСЂРµР±СѓРµС‚СЃСЏ СЂРѕР»СЊ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°.','РќР°Р·Р°Рґ РЅР° РїР°РЅРµР»СЊ','/dashboard'));
  const revenue = state.adminRevenue ? `<p class="small">РўРѕРєРµРЅС‹: ${state.adminRevenue.tokens_total} В· OpenAI: в‚¬${state.adminRevenue.estimated_openai_cost_eur} В· Stripe: в‚¬${state.adminRevenue.stripe_revenue_eur} В· РњР°СЂР¶Р°: ${state.adminRevenue.margin_percent}%</p>` : '<p class="small">Р—Р°РіСЂСѓР·РёС‚Рµ РїР°РЅРµР»СЊ РІС‹СЂСѓС‡РєРё.</p>';
  return appLayout('/admin','РђРґРјРёРЅ',`<section class="grid-2"><article class="card"><h2>РџРѕР»СЊР·РѕРІР°С‚РµР»Рё</h2><button id="adminUsersBtn" class="btn btn-primary">Р—Р°РіСЂСѓР·РёС‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№</button><div style="margin-top:10px;">${adminUsersTable()}</div></article><article class="card"><h2>РўР°СЂРёС„С‹ Рё РєСЂРµРґРёС‚С‹</h2>${field('adminUserId','ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ')}${selectField('adminPlan','РўР°СЂРёС„','free',[{value:'free',label:'Free'},{value:'light',label:'Light'},{value:'pro',label:'Pro'},{value:'agency',label:'Agency'}])}${field('adminDelta','Р·РјРµРЅРµРЅРёРµ РєСЂРµРґРёС‚РѕРІ','number','0')}<div class="cta-row"><button id="adminSetPlanBtn" class="btn btn-secondary">РЈСЃС‚Р°РЅРѕРІРёС‚СЊ С‚Р°СЂРёС„</button><button id="adminCreditsBtn" class="btn btn-ghost">Р·РјРµРЅРёС‚СЊ РєСЂРµРґРёС‚С‹</button></div></article><article class="card"><h2>РџР°РЅРµР»СЊ РІС‹СЂСѓС‡РєРё</h2>${revenue}<button id="adminRevenueBtn" class="btn btn-primary">РћР±РЅРѕРІРёС‚СЊ РІС‹СЂСѓС‡РєСѓ</button></article><article class="card"><h2>Р”РµР№СЃС‚РІРёСЏ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°</h2><div class="cta-row"><button id="adminGenBlogBtn" class="btn btn-secondary">РЎРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ СЃС‚Р°С‚СЊСЋ</button><button id="adminRunPlanBtn" class="btn btn-ghost">Р—Р°РїСѓСЃС‚РёС‚СЊ РєРѕРЅС‚РµРЅС‚-РїР»Р°РЅ</button></div></article></section>`);
}

function page(path) {
  const routes = { '/login': pageLogin, '/dashboard': pageDashboard, '/create': pageCreate, '/connections': pageConnections, '/history': pageHistory, '/billing': pageBilling, '/settings': pageSettings, '/admin': pageAdmin, '/blog': pageBlog, '/contact': pageContact };
  return (routes[path] || pageDashboard)();
}

async function preload(path) {
  if (!state.token) return;
  if (path === '/connections') state.connections = await api('/api/connections');
  if (path === '/history') state.posts = await api('/api/posts');
  if (path === '/billing' || path === '/dashboard') state.plans = await api('/api/plans');
  if (path === '/dashboard') {
    state.connections = await api('/api/connections');
    state.posts = await api('/api/posts');
  }
  if (path === '/blog') state.blog = await api('/api/blog/posts');
  if (path === '/admin' && state.user?.role === 'admin') { state.adminUsers = await api('/api/admin/users'); state.adminRevenue = await api('/api/admin/revenue'); }
}
async function loadBase() { state.user = await api('/api/me'); state.billing = state.user.billing; state.projects = await api('/api/projects'); }
function bindCommon() {
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) logoutBtn.onclick = () => { state.token = ''; localStorage.removeItem('token'); state.user = null; nav('/login'); };
  const themeToggle = document.getElementById('themeToggleBtn');
  if (themeToggle) themeToggle.onclick = () => { setTheme(state.theme === 'dark' ? 'light' : 'dark'); render(); };
}

async function bind() {
  bindCommon();

  const oauthGoogleBtn = document.getElementById('oauthGoogleBtn');
  if (oauthGoogleBtn && !oauthGoogleBtn.disabled) oauthGoogleBtn.onclick = () => { window.location.href = `${API_BASE}/api/auth/oauth/google/start`; };
  const oauthFacebookBtn = document.getElementById('oauthFacebookBtn');
  if (oauthFacebookBtn && !oauthFacebookBtn.disabled) oauthFacebookBtn.onclick = () => { window.location.href = `${API_BASE}/api/auth/oauth/facebook/start`; };

  const authSwitchBtn = document.getElementById('authSwitchBtn');
  if (authSwitchBtn) authSwitchBtn.onclick = () => {
    state.authMode = state.authMode === 'login' ? 'register' : 'login';
    state.notice = null;
    render();
  };

  const focusAuthEmail = () => {
    setTimeout(() => {
      const emailInput = document.getElementById('authEmail');
      if (emailInput) {
        emailInput.focus();
        emailInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 0);
  };

  const heroRegisterBtn = document.getElementById('heroRegisterBtn');
  if (heroRegisterBtn) heroRegisterBtn.onclick = () => {
    state.authMode = 'register';
    state.notice = null;
    render();
    focusAuthEmail();
  };

  const finalRegisterBtn = document.getElementById('finalRegisterBtn');
  if (finalRegisterBtn) finalRegisterBtn.onclick = () => {
    state.authMode = 'register';
    state.notice = null;
    render();
    focusAuthEmail();
  };

  const finalPricingBtn = document.getElementById('finalPricingBtn');
  if (finalPricingBtn) finalPricingBtn.onclick = () => nav('/billing');

  const authSubmitBtn = document.getElementById('authSubmitBtn');
  if (authSubmitBtn) authSubmitBtn.onclick = async () => {
    const email = document.getElementById('authEmail')?.value.trim().toLowerCase();
    const password = document.getElementById('authPassword')?.value || '';
    const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!email || !emailRe.test(email)) {
      state.notice = { type: 'error', text: 'Введите корректный email.' };
      render();
      return;
    }
    if (password.length < 8) {
      state.notice = { type: 'error', text: 'Пароль должен быть не короче 8 символов.' };
      render();
      return;
    }

    try {
      const endpoint = state.authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const data = await api(endpoint, { method: 'POST', body: JSON.stringify({ email, password }) });
      state.token = data.token;
      localStorage.setItem('token', data.token);
      await loadBase();
      state.notice = { type: 'ok', text: state.authMode === 'login' ? 'Вход выполнен успешно.' : 'Аккаунт создан. Подключите Facebook на следующем шаге.' };
      nav('/connections');
    } catch (e) {
      const raw = String(e.message || 'Ошибка авторизации');
      let text = 'Не удалось выполнить вход. Проверьте email и пароль.';
      if (raw.toLowerCase().includes('существует') || raw.toLowerCase().includes('already')) {
        text = 'Этот email уже зарегистрирован. Войдите в аккаунт.';
      } else if (raw.toLowerCase().includes('не короче') || raw.toLowerCase().includes('short')) {
        text = 'Пароль должен быть не короче 8 символов.';
      } else if (raw.toLowerCase().includes('неверный') || raw.toLowerCase().includes('invalid')) {
        text = 'Неверный email или пароль.';
      }
      state.notice = { type: 'error', text };
      render();
    }
  };

  const startManagerBtn = document.getElementById('startManagerBtn');
  if (startManagerBtn) startManagerBtn.onclick = async () => {
    try {
      const projectRaw = document.getElementById('managerProject').value;
      const business_type = document.getElementById('managerBusiness').value.trim();
      const niche = document.getElementById('managerNiche').value.trim();
      const goal = document.getElementById('managerGoal').value.trim();
      const language = document.getElementById('managerLang').value;
      const hasConnectedAccount = (state.connections || []).some((c) => isConnectionReady(c));
      if (!hasConnectedAccount) throw new Error('Сначала подключите Facebook/Instagram в разделе "Подключения".');
      if (!business_type || !niche || !goal) throw new Error('Заполните поля "Тип бизнеса", "Ниша" и "Цель".');
      const r = await api('/api/ai-smm-manager/start', { method: 'POST', body: JSON.stringify({ project_id: projectRaw ? Number(projectRaw) : null, business_type, niche, goal, language }) });
      const created = r?.result?.created_plan_items ?? null;
      const existing = r?.result?.existing_future_items ?? 0;
      const gen = r?.result?.generated_posts ?? 0;
      if (!created && existing > 0) {
        state.notice = { type: 'ok', text: `Контент-план уже создан (будущих публикаций: ${existing}). ${gen ? `Подготовлено постов: ${gen}. ` : ''}Для ускорения нажмите "План на неделю".` };
      } else {
        const days = Number(created || 30);
        state.notice = { type: 'ok', text: `Стратегия на ${days} дней создана. ${gen ? `Сразу подготовлено постов: ${gen}. ` : ''}Остальные можно подготовить кнопкой "План на неделю".` };
      }
      nav('/history');
    } catch (e) { state.notice = { type: 'error', text: e.message }; render(); }
  };

  const goConnectionsBtn = document.getElementById('goConnectionsBtn'); if (goConnectionsBtn) goConnectionsBtn.onclick = () => nav('/connections');
  const goCreateBtn = document.getElementById('goCreateBtn'); if (goCreateBtn) goCreateBtn.onclick = () => nav('/create');
  const goBillingBtn = document.getElementById('goBillingBtn'); if (goBillingBtn) goBillingBtn.onclick = () => nav('/billing');
  const strategyBtn = document.getElementById('strategyBtn'); if (strategyBtn) strategyBtn.onclick = () => document.getElementById('startManagerBtn')?.click();
  const postTodayBtn = document.getElementById('postTodayBtn');
  if (postTodayBtn) postTodayBtn.onclick = async () => {
    try {
      const projectRaw = document.getElementById('managerProject')?.value || '';
      await api('/api/content-plan/materialize', { method: 'POST', body: JSON.stringify({ project_id: projectRaw ? Number(projectRaw) : null, days: 1, limit: 3 }) });
      state.notice = { type: 'ok', text: 'Пост(ы) на сегодня поставлены в очередь и скоро появятся в истории.' };
      nav('/history');
    } catch (e) { state.notice = { type: 'error', text: e.message }; render(); }
  };

  const scheduleWeekBtn = document.getElementById('scheduleWeekBtn');
  if (scheduleWeekBtn) scheduleWeekBtn.onclick = async () => {
    try {
      const projectRaw = document.getElementById('managerProject')?.value || '';
      await api('/api/content-plan/materialize', { method: 'POST', body: JSON.stringify({ project_id: projectRaw ? Number(projectRaw) : null, days: 7, limit: 20 }) });
      state.notice = { type: 'ok', text: 'План на неделю поставлен в очередь: посты будут сгенерированы и запланированы автоматически.' };
      nav('/history');
    } catch (e) { state.notice = { type: 'error', text: e.message }; render(); }
  };
  const createProjectInlineBtn = document.getElementById('createProjectInlineBtn');
  if (createProjectInlineBtn) createProjectInlineBtn.onclick = async () => {
    try {
      const name = document.getElementById('dashboardProjectName').value.trim();
      if (name.length < 3) throw new Error('Название проекта должно быть минимум 3 символа.');
      await api('/api/projects', { method: 'POST', body: JSON.stringify({ name }) });
      await loadBase();
      state.notice = { type: 'ok', text: 'Проект создан.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message };
      render();
    }
  };

  document.querySelectorAll('[data-project-edit]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        const id = Number(btn.dataset.projectEdit);
        const current = btn.dataset.projectName || '';
        const next = prompt('Новое название проекта:', current);
        if (next === null) return; // cancel
        const name = String(next).trim();
        if (name.length < 3) throw new Error('Название проекта должно быть минимум 3 символа.');
        await api(`/api/projects/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) });
        await loadBase();
        state.notice = { type: 'ok', text: 'Проект переименован.' };
        render();
      } catch (e) {
        state.notice = { type: 'error', text: e.message };
        render();
      }
    };
  });
  const createProjectFromCreateBtn = document.getElementById('createProjectFromCreateBtn');
  if (createProjectFromCreateBtn) createProjectFromCreateBtn.onclick = async () => {
    try {
      const input = document.getElementById('wNewProject');
      const name = (input?.value || '').trim();
      if (name.length < 3) throw new Error('Название проекта должно быть минимум 3 символа.');
      createProjectFromCreateBtn.disabled = true;
      const created = await api('/api/projects', { method: 'POST', body: JSON.stringify({ name }) });
      await loadBase();
      state.createWizard.projectId = String(created?.id || state.projects[state.projects.length - 1]?.id || '');
      state.notice = { type: 'ok', text: 'Проект создан и выбран в мастере.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message };
      render();
    } finally {
      createProjectFromCreateBtn.disabled = false;
    }
  };
  const wCategoryEl = document.getElementById('wCategory');
  if (wCategoryEl) wCategoryEl.onchange = () => { state.createWizard.category = wCategoryEl.value; render(); };
  const wToneEl = document.getElementById('wTone');
  if (wToneEl) wToneEl.onchange = () => { state.createWizard.tone = wToneEl.value; render(); };
  const wModeEl = document.getElementById('wMode');
  if (wModeEl) wModeEl.onchange = () => { state.createWizard.mode = wModeEl.value; render(); };
  document.querySelectorAll('[data-topic-template]').forEach((btn) => {
    btn.onclick = () => {
      const topic = (btn.getAttribute('data-topic-template') || '').trim();
      const topicInput = document.getElementById('wTopic');
      if (topicInput) topicInput.value = topic;
      state.createWizard.topic = topic;
      state.notice = null;
    };
  });

  const wPrev = document.getElementById('wPrev'); if (wPrev) wPrev.onclick = () => { state.createWizard.step = Math.max(1, state.createWizard.step - 1); render(); };
  const wNext = document.getElementById('wNext'); if (wNext) wNext.onclick = () => {
    const w = state.createWizard;
    if (w.step === 1) w.projectId = document.getElementById('wProject').value;
    if (w.step === 2) {
      w.platforms.facebook = !!document.getElementById('wFb')?.checked;
      w.platforms.instagram = !!document.getElementById('wIg')?.checked;
      if (!w.platforms.facebook && !w.platforms.instagram) { state.notice = { type: 'error', text: 'Выберите хотя бы одну платформу.' }; return render(); }
    }
    if (w.step === 3) {
      w.category = document.getElementById('wCategory').value.trim();
      w.topic = document.getElementById('wTopic').value.trim();
      w.tone = document.getElementById('wTone').value;
      w.language = document.getElementById('wLang').value;
      w.mediaUrl = document.getElementById('wMedia').value.trim();
      if (!w.topic) { state.notice = { type: 'error', text: 'Тема обязательна.' }; return render(); }
      if (!w.previewText) {
        w.previewText = '';
      }
    }
    if (w.step === 4) {
      w.previewText = (document.getElementById('wPreviewText')?.value || '').trim();
      if (!w.previewText) { state.notice = { type: 'error', text: 'Добавьте текст в предпросмотре.' }; return render(); }
    }
    if (w.step === 5) {
      w.mode = document.getElementById('wMode')?.value || 'now';
      w.scheduleAt = document.getElementById('wSchedule')?.value || '';
    }
    w.step = Math.min(5, w.step + 1);
    render();
  };

  const wSubmit = document.getElementById('wSubmit');
  if (wSubmit) wSubmit.onclick = async () => {
    try {
      const w = state.createWizard;
      // Persist step 5 fields on submit as well (in case user didn't hit Next).
      w.mode = document.getElementById('wMode')?.value || w.mode || 'now';
      w.scheduleAt = document.getElementById('wSchedule')?.value || w.scheduleAt || '';
      w.previewText = (document.getElementById('wPreviewText')?.value || w.previewText || '').trim();

      const hasConnectedAccount = (state.connections || []).some((c) => isConnectionReady(c));
      if (!hasConnectedAccount) throw new Error('Сначала подключите Facebook/Instagram в разделе "Подключения".');
      if (!w.topic) throw new Error('Тема обязательна.');
      if (!w.previewText) throw new Error('Добавьте текст в предпросмотре.');

      const selectedPlatforms = [
        w.platforms.facebook ? 'facebook' : null,
        w.platforms.instagram ? 'instagram' : null,
      ].filter(Boolean);
      if (!selectedPlatforms.length) throw new Error('Выберите хотя бы одну платформу.');
      const project_id = Number(w.projectId || state.projects[0]?.id || 0) || null;
      const payloadBase = {
        project_id,
        topic: w.topic,
        category: w.category,
        tone: w.tone,
        language: w.language,
        media_url: w.mediaUrl || null,
        generated_text: w.previewText,
      };

      wSubmit.disabled = true;
      wSubmit.textContent = (w.mode === 'schedule') ? 'Планирую…' : 'Публикую…';

      if (w.mode === 'schedule') {
        if (!w.scheduleAt) throw new Error('Укажите дату и время для планирования.');
        const scheduleAtIso = new Date(w.scheduleAt).toISOString();
        for (const platform of selectedPlatforms) {
          const payload = { ...payloadBase, platform, schedule_at: scheduleAtIso };
          await api('/api/generate', { method: 'POST', body: JSON.stringify(payload) });
        }
        state.notice = { type: 'ok', text: selectedPlatforms.length > 1 ? 'Посты созданы и запланированы для Facebook и Instagram.' : 'Пост создан и запланирован.' };
        nav('/history');
        return;
      }

      // mode=draft: generate content only, without publishing.
      if (w.mode === 'draft') {
        for (const platform of selectedPlatforms) {
          const payload = { ...payloadBase, platform, save_as_draft: true };
          await api('/api/generate', { method: 'POST', body: JSON.stringify(payload) });
        }
        state.notice = { type: 'ok', text: selectedPlatforms.length > 1 ? 'Черновики созданы для Facebook и Instagram.' : 'Черновик сохранён. Отредактировать и опубликовать можно в истории.' };
        nav('/history');
        return;
      }

      // mode=now: generate content and then call publish endpoint.
      let sharedMediaUrl = (w.mediaUrl || '').trim() || null;
      const publishErrors = [];
      for (const platform of selectedPlatforms) {
        const payload = { ...payloadBase, platform, media_url: sharedMediaUrl };
        const created = await api('/api/generate', { method: 'POST', body: JSON.stringify(payload) });
        const postId = created?.id;
        if (!postId) throw new Error(`Не удалось создать пост для ${platform}.`);
        if (!sharedMediaUrl && created?.media_url) sharedMediaUrl = created.media_url;
        try {
          await api(`/api/posts/${postId}/publish`, { method: 'POST', body: '{}' });
        } catch (pubErr) {
          publishErrors.push(`${platform === 'facebook' ? 'Facebook' : 'Instagram'}: ${pubErr?.message || 'ошибка публикации'}`);
        }
      }
      if (publishErrors.length) {
        throw new Error(`Часть публикаций не выполнена: ${publishErrors.join(' ; ')}`);
      }
      state.notice = { type: 'ok', text: selectedPlatforms.length > 1 ? 'Посты опубликованы в Facebook и Instagram.' : 'Пост опубликован.' };
      nav('/history');
    } catch (e) {
      let text = e.message || 'Ошибка публикации.';
      if (String(text).includes('OpenAI: недостаточно квоты')) {
        text = 'OpenAI: недостаточно квоты. Пополните лимит/баланс в OpenAI или включите USE_MOCK_PROVIDERS=true для теста без ключей.';
      }
      state.notice = { type: 'error', text };
      render();
    } finally {
      try {
        const mode = document.getElementById('wMode')?.value || state.createWizard.mode || 'now';
        wSubmit.disabled = false;
        wSubmit.textContent = mode === 'schedule' ? 'Создать и запланировать' : (mode === 'draft' ? 'Сохранить как черновик' : 'Создать и опубликовать');
      } catch {}
    }
  };

  const startMetaConnect = async () => {
    const r = await api('/api/integrations/meta/connect', { method: 'POST', body: '{}' });
    location.href = r.oauth_url;
  };
  const connectMetaBtn = document.getElementById('connectMetaBtn');
  if (connectMetaBtn) connectMetaBtn.onclick = async () => startMetaConnect();
  const connectDemoBtn = document.getElementById('connectDemoBtn'); if (connectDemoBtn) connectDemoBtn.onclick = async () => { await api('/api/connections/meta/mock-connect', { method: 'POST', body: '{}' }); state.connections = await api('/api/connections'); render(); };
  document.querySelectorAll('[data-disconnect]').forEach((b) => b.onclick = async () => {
    if (!confirm('Отключить интеграцию Meta?')) return;
    await api(`/api/connections/${b.dataset.disconnect}/disconnect`, { method: 'POST', body: '{}' });
    state.connections = await api('/api/connections');
    state.notice = { type: 'ok', text: 'Интеграция отключена.' };
    render();
  });
  document.querySelectorAll('[data-refresh]').forEach((b) => b.onclick = async () => {
    await api(`/api/connections/${b.dataset.refresh}/refresh-token`, { method: 'POST', body: '{}' });
    state.connections = await api('/api/connections');
    state.notice = { type: 'ok', text: 'Статус подключения обновлён.' };
    render();
  });
  document.querySelectorAll('[data-copy-tech]').forEach((b) => b.onclick = async () => {
    const id = Number(b.dataset.copyTech);
    const connection = (state.connections || []).find((x) => Number(x.id) === id);
    if (!connection) return;
    const text = connection.tech_log || JSON.stringify(connection, null, 2);
    try {
      await navigator.clipboard.writeText(text);
      state.notice = { type: 'ok', text: 'Тех.лог скопирован в буфер обмена.' };
    } catch {
      state.notice = { type: 'error', text: 'Не удалось скопировать тех.лог.' };
    }
    render();
  });
  document.querySelectorAll('[data-open-details]').forEach((b) => b.onclick = () => {
    const card = b.closest('.card');
    const details = card ? card.querySelector('details') : null;
    if (!details) return;
    details.open = true;
    details.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });

  // Meta Page picker (explicit Page selection for multi-Page accounts).
  const closePicker = () => {
    state.connectionPicker.open = false;
    state.connectionPicker.loading = false;
    state.connectionPicker.pages = [];
    state.connectionPicker.selectedPageId = '';
    state.connectionPicker.error = '';
    state.connectionPicker.filter = 'all';
    state.connectionPicker.query = '';
  };

  const openPagePicker = async (id) => {
    try {
      state.connectionPicker.open = true;
      state.connectionPicker.connectionId = id;
      state.connectionPicker.loading = true;
      state.connectionPicker.pages = [];
      state.connectionPicker.selectedPageId = '';
      state.connectionPicker.error = '';
      state.connectionPicker.filter = 'all';
      state.connectionPicker.query = '';
      render();

      const r = await api(`/api/integrations/meta/pages?connection_id=${encodeURIComponent(id)}`);
      state.connectionPicker.pages = r.pages || [];
      state.connectionPicker.loading = false;
      // Preselect page that has IG if possible.
      const preferred = (state.connectionPicker.pages || []).find((p) => p.has_ig) || state.connectionPicker.pages[0];
      if (preferred) state.connectionPicker.selectedPageId = String(preferred.page_id || '');
      render();
    } catch (e) {
      state.connectionPicker.loading = false;
      state.connectionPicker.error = e.message || 'Не удалось загрузить страницы.';
      render();
    }
  };

  document.querySelectorAll('[data-primary-action]').forEach((b) => b.onclick = async () => {
    const action = String(b.dataset.primaryAction || '');
    const id = Number(b.dataset.connectionId || 0);
    try {
      if (action === 'connect' || action === 'reconnect') {
        await startMetaConnect();
        return;
      }
      if (action === 'pick_page') {
        await openPagePicker(id);
        return;
      }
      if (action === 'test') {
        const r = await api(`/api/connections/${id}/test-publish`, { method: 'POST', body: '{}' });
        state.connections = await api('/api/connections');
        const mode = (r && r.mode) ? String(r.mode) : '';
        const postId = (r && r.post_id) ? String(r.post_id) : '';
        const text = postId
          ? `Тестовая публикация отправлена (${mode || 'real'}). Post ID: ${postId}`
          : 'Тест публикации пройден.';
        state.notice = { type: 'ok', text };
        render();
        return;
      }
      await api(`/api/connections/${id}/refresh-token`, { method: 'POST', body: '{}' });
      state.connections = await api('/api/connections');
      state.notice = { type: 'ok', text: 'Повторная проверка выполнена.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Ошибка действия интеграции.' };
      render();
    }
  });

  const pickerBackdrop = document.getElementById('connectionPickerBackdrop');
  if (pickerBackdrop) pickerBackdrop.onclick = (e) => {
    if (e.target === pickerBackdrop) { closePicker(); render(); }
  };

  const closePickerBtn = document.getElementById('closePickerBtn');
  if (closePickerBtn) closePickerBtn.onclick = () => { closePicker(); render(); };

  document.querySelectorAll('input[name="pagePick"]').forEach((el) => el.onchange = () => {
    state.connectionPicker.selectedPageId = el.value;
    const saveBtn = document.getElementById('savePickedPageBtn');
    if (saveBtn) saveBtn.disabled = !state.connectionPicker.selectedPageId;
    const addBtn = document.getElementById('addPickedPageBtn');
    if (addBtn) addBtn.disabled = !state.connectionPicker.selectedPageId;
  });

  const applyFilterBtnState = () => {
    const a = document.getElementById('filterAllBtn');
    const w = document.getElementById('filterWithIgBtn');
    const n = document.getElementById('filterWithoutIgBtn');
    const f = state.connectionPicker.filter;
    const activeClass = 'btn btn-secondary';
    const normalClass = 'btn btn-ghost';
    if (a) a.className = f === 'all' ? activeClass : normalClass;
    if (w) w.className = f === 'with_ig' ? activeClass : normalClass;
    if (n) n.className = f === 'without_ig' ? activeClass : normalClass;
  };

  const filterAllBtn = document.getElementById('filterAllBtn');
  if (filterAllBtn) filterAllBtn.onclick = () => { state.connectionPicker.filter = 'all'; applyFilterBtnState(); render(); };
  const filterWithIgBtn = document.getElementById('filterWithIgBtn');
  if (filterWithIgBtn) filterWithIgBtn.onclick = () => { state.connectionPicker.filter = 'with_ig'; applyFilterBtnState(); render(); };
  const filterWithoutIgBtn = document.getElementById('filterWithoutIgBtn');
  if (filterWithoutIgBtn) filterWithoutIgBtn.onclick = () => { state.connectionPicker.filter = 'without_ig'; applyFilterBtnState(); render(); };

  const pageSearchInput = document.getElementById('pageSearchInput');
  if (pageSearchInput) {
    pageSearchInput.value = state.connectionPicker.query || '';
    pageSearchInput.oninput = () => { state.connectionPicker.query = pageSearchInput.value; render(); };
    setTimeout(() => { try { pageSearchInput.focus(); } catch {} }, 0);
  }
  applyFilterBtnState();

  const refreshPagesBtn = document.getElementById('refreshPagesBtn');
  if (refreshPagesBtn) refreshPagesBtn.onclick = async () => {
    try {
      const id = state.connectionPicker.connectionId;
      if (!id) return;
      state.connectionPicker.loading = true;
      state.connectionPicker.error = '';
      render();
      const r = await api(`/api/integrations/meta/pages?connection_id=${encodeURIComponent(id)}`);
      state.connectionPicker.pages = r.pages || [];
      state.connectionPicker.loading = false;
      render();
    } catch (e) {
      state.connectionPicker.loading = false;
      state.connectionPicker.error = e.message || 'Не удалось обновить список.';
      render();
    }
  };

  const savePickedPageBtn = document.getElementById('savePickedPageBtn');
  if (savePickedPageBtn) savePickedPageBtn.onclick = async () => {
    try {
      const id = state.connectionPicker.connectionId;
      const page_id = state.connectionPicker.selectedPageId;
      if (!id || !page_id) return;
      savePickedPageBtn.disabled = true;
      await api('/api/integrations/meta/select-page', { method: 'POST', body: JSON.stringify({ connection_id: id, page_id }) });
      state.connections = await api('/api/connections');
      closePicker();
      state.notice = { type: 'ok', text: 'Страница выбрана.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось сохранить выбор.' };
      render();
    } finally {
      savePickedPageBtn.disabled = false;
    }
  };

  const addPickedPageBtn = document.getElementById('addPickedPageBtn');
  if (addPickedPageBtn) addPickedPageBtn.onclick = async () => {
    try {
      const id = state.connectionPicker.connectionId;
      const page_id = state.connectionPicker.selectedPageId;
      if (!id || !page_id) return;
      addPickedPageBtn.disabled = true;
      await api('/api/connections/meta/add-page', { method: 'POST', body: JSON.stringify({ source_connection_id: id, page_id }) });
      state.connections = await api('/api/connections');
      closePicker();
      state.notice = { type: 'ok', text: 'Страница добавлена как отдельное подключение.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось добавить подключение.' };
      render();
    } finally {
      addPickedPageBtn.disabled = false;
    }
  };

  const openPostEditor = async (id) => {
    if (!id) return;
    state.postEditor = { open: true, saving: false, post: null, error: '', loading: true };
    render();
    try {
      const post = await api(`/api/posts/${id}`);
      state.postEditor = { open: true, saving: false, post, error: '', loading: false };
      render();
    } catch (e) {
      state.postEditor = { open: true, saving: false, post: null, error: e.message || 'Не удалось загрузить пост.', loading: false };
      render();
    }
  };
  const closePostEditor = () => {
    state.postEditor = { open: false, saving: false, post: null, error: '' };
    render();
  };

  const postEditBackdrop = document.getElementById('postEditBackdrop');
  if (postEditBackdrop) postEditBackdrop.onclick = (e) => { if (e.target && e.target.id === 'postEditBackdrop') closePostEditor(); };
  const closePostEditBtn = document.getElementById('closePostEditBtn');
  if (closePostEditBtn) closePostEditBtn.onclick = closePostEditor;

  const clearScheduleBtn = document.getElementById('clearScheduleBtn');
  if (clearScheduleBtn) clearScheduleBtn.onclick = () => {
    const el = document.getElementById('editSchedule');
    if (el) el.value = '';
  };

  const savePostEditBtn = document.getElementById('savePostEditBtn');
  if (savePostEditBtn) savePostEditBtn.onclick = async () => {
    const post = state.postEditor?.post;
    if (!post?.id) return;
    const topic = (document.getElementById('editTopic')?.value || '').trim();
    if (!topic) {
      state.postEditor = { ...state.postEditor, error: 'Введите тему поста.' };
      render();
      return;
    }
    const payload = {
      topic,
      generated_text: (document.getElementById('editText')?.value || '').trim(),
      platform: (document.getElementById('editPlatform')?.value || 'instagram').trim(),
      media_url: (document.getElementById('editMedia')?.value || '').trim(),
      schedule_at: null,
    };
    const scheduleValue = (document.getElementById('editSchedule')?.value || '').trim();
    if (scheduleValue) {
      payload.schedule_at = new Date(scheduleValue).toISOString();
    }
    state.postEditor = { ...state.postEditor, saving: true, error: '' };
    render();
    try {
      await api(`/api/posts/${post.id}`, { method: 'PATCH', body: JSON.stringify(payload) });
      state.posts = await api('/api/posts');
      state.notice = { type: 'ok', text: 'Пост обновлен.' };
      state.postEditor = { open: false, saving: false, post: null, error: '' };
      render();
    } catch (e) {
      state.postEditor = { ...state.postEditor, saving: false, error: e.message || 'Не удалось сохранить пост.' };
      render();
    }
  };

  document.querySelectorAll('[data-edit-post]').forEach((b) => b.onclick = async () => {
    const id = Number(b.dataset.editPost || b.getAttribute('data-edit-post'));
    await openPostEditor(id);
  });

  const dropScheduleForColumn = (post, colKey) => {
    if (!post || colKey === 'draft') return null;
    const base = post.schedule_at ? new Date(post.schedule_at) : new Date(`${colKey}T12:00:00`);
    const safeBase = Number.isNaN(base.getTime()) ? new Date(`${colKey}T12:00:00`) : base;
    const t = new Date(`${colKey}T00:00:00`);
    t.setHours(safeBase.getHours(), safeBase.getMinutes(), 0, 0);
    return t.toISOString();
  };

  document.querySelectorAll('[data-post-card]').forEach((card) => {
    card.ondragstart = (e) => {
      const id = card.dataset.postCard;
      if (!id) return;
      e.dataTransfer.setData('text/plain', id);
      card.classList.add('dragging');
    };
    card.ondragend = () => {
      card.classList.remove('dragging');
      document.querySelectorAll('[data-drop-col].drop-hover').forEach((x) => x.classList.remove('drop-hover'));
    };
  });

  document.querySelectorAll('[data-drop-col]').forEach((col) => {
    col.ondragover = (e) => { e.preventDefault(); col.classList.add('drop-hover'); };
    col.ondragleave = () => col.classList.remove('drop-hover');
    col.ondrop = async (e) => {
      e.preventDefault();
      col.classList.remove('drop-hover');
      const id = Number(e.dataTransfer.getData('text/plain') || 0);
      if (!id) return;
      const post = (state.posts || []).find((p) => p.id === id);
      if (!post || post.published_at || String(post.status || '').toLowerCase() === 'done') return;
      const payload = {
        schedule_at: dropScheduleForColumn(post, col.dataset.dropCol || 'draft'),
      };
      try {
        await api(`/api/posts/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
        state.posts = await api('/api/posts');
        state.notice = { type: 'ok', text: 'Планировщик обновлен.' };
        render();
      } catch (err) {
        state.notice = { type: 'error', text: err.message || 'Не удалось перенести пост.' };
        render();
      }
    };
  });

  const closePostViewer = () => { state.postViewer = { open: false, loading: false, post: null, error: '' }; render(); };
  const closePostViewerBtn = document.getElementById('closePostViewerBtn');
  if (closePostViewerBtn) closePostViewerBtn.onclick = closePostViewer;
  const postViewerBackdrop = document.getElementById('postViewerBackdrop');
  if (postViewerBackdrop) postViewerBackdrop.onclick = (e) => { if (e.target && e.target.id === 'postViewerBackdrop') closePostViewer(); };

  document.querySelectorAll('[data-view-post]').forEach((b) => b.onclick = async () => {
    const id = Number(b.dataset.viewPost || b.getAttribute('data-view-post'));
    if (!id) return;
    state.postViewer = { open: true, loading: true, post: null, error: '' };
    render();
    try {
      const post = await api(`/api/posts/${id}`);
      state.postViewer = { open: true, loading: false, post, error: '' };
      render();
    } catch (e) {
      state.postViewer = { open: true, loading: false, post: null, error: e.message || 'Не удалось загрузить пост.' };
      render();
    }
  });

  document.querySelectorAll('[data-retry]').forEach((b) => b.onclick = async () => {
    const p = state.posts.find((x) => x.id === Number(b.dataset.retry));
    if (!p) return;
    await api('/api/generate', { method: 'POST', body: JSON.stringify({ project_id: p.project_id, topic: p.topic, category: p.category || 'business' }) });
    state.posts = await api('/api/posts');
    render();
  });

  document.querySelectorAll('[data-publish-now]').forEach((b) => b.onclick = async () => {
    const id = Number(b.dataset.publishNow || b.getAttribute('data-publish-now'));
    if (!id) return;
    b.disabled = true;
    try {
      await api(`/api/posts/${id}/publish`, { method: 'POST', body: '{}' });
      state.posts = await api('/api/posts');
      state.notice = { type: 'ok', text: 'Пост отправлен в публикацию.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось опубликовать пост.' };
      render();
    }
  });

  const checkoutSubscription = async (plan) => {
    try {
      const r = await api('/api/billing/checkout/subscription', { method: 'POST', body: JSON.stringify({ plan }) });
      location.href = r.checkout_url;
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось открыть оплату. Проверьте настройки Stripe.' };
      render();
    }
  };
  document.querySelectorAll('[data-upgrade]').forEach((btn) => btn.onclick = () => checkoutSubscription(btn.dataset.upgrade));

  const portalBtn = document.querySelector('[data-portal]');
  if (portalBtn) portalBtn.onclick = async () => {
    try {
      const r = await api('/api/billing/portal', { method: 'POST', body: '{}' });
      location.href = r.portal_url;
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось открыть портал подписки. Проверьте настройки Stripe.' };
      render();
    }
  };

  const saveProfileBtn = document.getElementById('saveProfileBtn'); if (saveProfileBtn) saveProfileBtn.onclick = async () => { await api('/api/settings/profile', { method: 'PATCH', body: JSON.stringify({ email: document.getElementById('profileEmail').value.trim() }) }); state.notice = { type: 'ok', text: 'РџСЂРѕС„РёР»СЊ РѕР±РЅРѕРІР»С‘РЅ.' }; await loadBase(); render(); };
  const savePassBtn = document.getElementById('savePassBtn'); if (savePassBtn) savePassBtn.onclick = async () => { await api('/api/settings/password', { method: 'POST', body: JSON.stringify({ current_password: document.getElementById('curPass').value, new_password: document.getElementById('newPass').value }) }); state.notice = { type: 'ok', text: 'РџР°СЂРѕР»СЊ РѕР±РЅРѕРІР»С‘РЅ.' }; render(); };

  const adminUsersBtn = document.getElementById('adminUsersBtn'); if (adminUsersBtn) adminUsersBtn.onclick = async () => { state.adminUsers = await api('/api/admin/users'); render(); };
  const adminSetPlanBtn = document.getElementById('adminSetPlanBtn'); if (adminSetPlanBtn) adminSetPlanBtn.onclick = async () => { const uid = document.getElementById('adminUserId').value; await api(`/api/admin/users/${uid}/plan`, { method: 'PATCH', body: JSON.stringify({ plan: document.getElementById('adminPlan').value }) }); state.adminUsers = await api('/api/admin/users'); render(); };
  const adminCreditsBtn = document.getElementById('adminCreditsBtn'); if (adminCreditsBtn) adminCreditsBtn.onclick = async () => { const uid = document.getElementById('adminUserId').value; await api(`/api/admin/users/${uid}/credits`, { method: 'PATCH', body: JSON.stringify({ delta: Number(document.getElementById('adminDelta').value || 0) }) }); state.adminUsers = await api('/api/admin/users'); render(); };
  const adminRevenueBtn = document.getElementById('adminRevenueBtn'); if (adminRevenueBtn) adminRevenueBtn.onclick = async () => { state.adminRevenue = await api('/api/admin/revenue'); render(); };
  const adminGenBlogBtn = document.getElementById('adminGenBlogBtn'); if (adminGenBlogBtn) adminGenBlogBtn.onclick = async () => { await api('/api/admin/blog/generate', { method: 'POST', body: '{}' }); render(); };
  const adminRunPlanBtn = document.getElementById('adminRunPlanBtn'); if (adminRunPlanBtn) adminRunPlanBtn.onclick = async () => { await api('/api/content-plan/run-due', { method: 'POST', body: '{}' }); render(); };
}

async function render() {
  const currentRender = ++renderVersion;
  let path = location.pathname.replace(/\/$/, '') || '/';
  const query = new URLSearchParams(location.search);
  if (path === '/') { history.replaceState({}, '', state.token ? '/dashboard' : '/login'); path = location.pathname.replace(/\/$/, '') || '/'; }
  if (path === '/login') {
    if (!state.authProviders) await loadAuthProviders();
    const oauthToken = query.get('oauth_token');
    const oauthError = query.get('oauth_error');

    if (oauthToken) {
      state.token = oauthToken;
      localStorage.setItem('token', oauthToken);
      try {
        await loadBase();
        state.notice = { type: 'ok', text: 'Вход выполнен успешно.' };
        history.replaceState({}, '', '/dashboard');
        path = '/dashboard';
      } catch {
        state.token = '';
        localStorage.removeItem('token');
        state.notice = { type: 'error', text: 'Не удалось выполнить вход. Попробуйте снова.' };
        history.replaceState({}, '', '/login');
        path = '/login';
      }
    } else if (oauthError) {
      state.notice = { type: 'error', text: 'Социальный вход временно недоступен. Используйте email и пароль.' };
      history.replaceState({}, '', '/login');
      path = '/login';
    }
  }
  if (isAuthRoute(path) && !state.token) { history.replaceState({}, '', '/login'); path = '/login'; }
  if (path === '/connections') {
    const err = query.get('error');
    const msg = query.get('message');
    const status = query.get('status');
    if (query.get('connected') === '1') {
      state.notice = { type: 'ok', text: '\u0410\u043a\u043a\u0430\u0443\u043d\u0442 Facebook/Instagram \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d.' };
      history.replaceState({}, '', '/connections');
    } else if (err === 'state_invalid') {
      state.notice = { type: 'error', text: '\u041e\u0448\u0438\u0431\u043a\u0430 OAuth state. \u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u0441\u043d\u043e\u0432\u0430 \u0438\u0437 \u043f\u0430\u043d\u0435\u043b\u0438.' };
      history.replaceState({}, '', '/connections');
    } else if (err === 'oauth_denied') {
      state.notice = { type: 'error', text: '\u0412\u044b \u043e\u0442\u043c\u0435\u043d\u0438\u043b\u0438 \u0434\u043e\u0441\u0442\u0443\u043f Facebook. \u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435.' };
      history.replaceState({}, '', '/connections');
    } else if (err === 'token_exchange_failed') {
      let text = '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0442\u043e\u043a\u0435\u043d Facebook. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 FB_APP_ID/FB_APP_SECRET \u0438 Redirect URI.';
      if (status) text += ` (HTTP ${status})`;
      if (msg) text += `: ${msg}`;
      state.notice = { type: 'error', text };
      history.replaceState({}, '', '/connections');
    } else if (err === 'no_pages') {
      let text = '\u0423 \u044d\u0442\u043e\u0433\u043e Facebook-\u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430 \u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0445 \u0421\u0442\u0440\u0430\u043d\u0438\u0446. \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u0441 \u0421\u0442\u0440\u0430\u043d\u0438\u0446\u0435\u0439.';
      if (msg) text += ` (${msg})`;
      state.notice = { type: 'error', text };
      history.replaceState({}, '', '/connections');
    } else if (err === 'no_ig_business') {
      let text = '\u0421\u0442\u0440\u0430\u043d\u0438\u0446\u0430 Facebook \u043d\u0430\u0439\u0434\u0435\u043d\u0430, \u043d\u043e \u043d\u0435\u0442 Instagram Business. \u041f\u0440\u0438\u0432\u044f\u0436\u0438\u0442\u0435 IG Business \u043a \u0421\u0442\u0440\u0430\u043d\u0438\u0446\u0435.';
      if (msg) text += ` (${msg})`;
      state.notice = { type: 'error', text };
      history.replaceState({}, '', '/connections');
    } else if (err === 'meta_api_error') {
      let text = '\u041e\u0448\u0438\u0431\u043a\u0430 Meta API. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 permissions \u0432 Meta Developers.';
      if (msg) text += ` (${msg})`;
      state.notice = { type: 'error', text };
      history.replaceState({}, '', '/connections');
    }
  }
  try { if (isAuthRoute(path)) { await loadBase(); await preload(path); } } catch { state.token = ''; localStorage.removeItem('token'); history.replaceState({}, '', '/login'); path = '/login'; state.notice = { type: 'error', text: 'РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’РѕР№РґРёС‚Рµ СЃРЅРѕРІР°.' }; }
  if (currentRender !== renderVersion) return;
  document.getElementById('app').innerHTML = decodeMojibake(page(path));
  if (currentRender !== renderVersion) return;
  await bind(path);
}

window.addEventListener('popstate', () => render());
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-link]');
  if (!el) return;
  e.preventDefault();
  e.stopPropagation();
  nav(el.getAttribute('data-link'));
});
render();










