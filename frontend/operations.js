/* Operations Overview — Video Factory ops panel (UTF-8, standalone module).
 *
 * Deliberately separate from app.js: that file's admin block is mojibake-encoded,
 * so we do not edit it. This module renders into #operationsRoot on /operations
 * and reads ONLY real backend data:
 *   GET /api/factory-dashboard  -> infrastructure, queue, jobs, publications, alerts
 *   GET /api/readiness          -> backend/db readiness
 * Nothing here is faked: a value we cannot read is rendered as "Не удалось получить"
 * (Unknown), never as a green "OK".
 */
(function () {
  'use strict';

  var API_BASE = (function () {
    var saved = (localStorage.getItem('apiBase') || '').trim().replace(/\/+$/, '');
    var host = window.location.hostname || '';
    var isLocal = host === 'localhost' || host === '127.0.0.1';
    if (isLocal && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(saved)) return saved;
    return isLocal ? 'http://127.0.0.1:5000'
      : window.location.protocol + '//api.' + host.replace(/^www\./, '');
  })();

  function esc(v) {
    return String(v === null || v === undefined ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function get(path) {
    var token = localStorage.getItem('token') || '';
    return fetch(API_BASE + path, {
      headers: token ? { Authorization: 'Bearer ' + token } : {}
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  // ---- status vocabulary: Healthy | Degraded | Offline | Unknown -----------
  var S = {
    healthy: { label: 'Healthy', cls: 'ops-ok' },
    degraded: { label: 'Degraded', cls: 'ops-warn' },
    offline: { label: 'Offline', cls: 'ops-off' },
    unknown: { label: 'Unknown', cls: 'ops-unknown' }
  };

  function badge(kind) {
    var s = S[kind] || S.unknown;
    return '<span class="ops-badge ' + s.cls + '">' + s.label + '</span>';
  }

  function row(name, kind, detail) {
    return '<tr><td>' + esc(name) + '</td><td>' + badge(kind) + '</td><td class="ops-detail">'
      + (detail ? esc(detail) : '<span class="ops-muted">—</span>') + '</td></tr>';
  }

  function skeleton() {
    return '<div class="ops-card"><div class="ops-skel"></div><div class="ops-skel"></div>'
      + '<div class="ops-skel short"></div></div>';
  }

  function render(root, data, readiness, err) {
    if (err) {
      root.innerHTML = '<div class="ops-card ops-error"><h3>Не удалось загрузить Operations</h3>'
        + '<p class="ops-muted">' + esc(err.message || String(err)) + '</p>'
        + '<button class="btn btn-secondary" id="opsRetry" type="button">Повторить</button></div>';
      var rb = document.getElementById('opsRetry');
      if (rb) rb.onclick = function () { load(root); };
      return;
    }

    var infra = (data && data.infrastructure) || {};
    var ov = (data && data.overview) || {};
    var pubs = (data && data.publications) || {};
    var alerts = (data && data.alerts) || [];

    // Backend/DB: if factory-dashboard answered, the API and its DB queries work.
    var backend = data ? 'healthy' : 'unknown';
    var db = data ? 'healthy' : 'unknown';
    if (readiness && readiness.database && readiness.database.ok === false) db = 'offline';

    var redisOk = infra.redis && infra.redis.ok;
    var redis = infra.redis ? (redisOk ? 'healthy' : 'offline') : 'unknown';
    var workerOnline = infra.worker && infra.worker.online;
    var worker = infra.worker ? (workerOnline ? 'healthy' : 'offline') : 'unknown';
    var ffmpeg = infra.ffmpeg ? 'healthy' : 'unknown';

    var diskGb = (typeof infra.disk_free_gb === 'number') ? infra.disk_free_gb : null;
    var disk = diskGb === null ? 'unknown' : (diskGb < 2 ? 'offline' : (diskGb < 10 ? 'degraded' : 'healthy'));

    var qLen = (infra.render_queue_size === null || infra.render_queue_size === undefined)
      ? null : infra.render_queue_size;

    var failed = (ov.jobs_failed || 0) + (pubs.failed || 0);
    var health = [
      row('Backend API', backend, data ? 'отвечает' : 'нет ответа'),
      row('База данных', db, data ? 'запросы выполняются' : 'не проверено'),
      row('Redis', redis, infra.redis ? (redisOk ? 'подключён' : (infra.redis.error || 'недоступен')) : 'не проверено'),
      row('RQ worker', worker, infra.worker ? (workerOnline ? 'online' : 'offline — рендеры не выполняются') : 'не проверено'),
      row('FFmpeg', ffmpeg, infra.ffmpeg || 'не проверено'),
      row('Диск (free)', disk, diskGb === null ? 'не проверено' : diskGb + ' GB свободно')
    ].join('');

    var metrics = [
      ['Очередь рендера', qLen === null ? '<span class="ops-muted">Не удалось получить</span>' : qLen],
      ['Выполняется задач', ov.jobs_processing === undefined ? '<span class="ops-muted">—</span>' : ov.jobs_processing],
      ['В очереди задач', ov.jobs_pending === undefined ? '<span class="ops-muted">—</span>' : ov.jobs_pending],
      ['Ошибок (рендер + публикация)', failed ? '<strong class="ops-bad">' + failed + '</strong>' : '0'],
      ['Опубликовано 7д / 30д', (ov.published_7d || 0) + ' / ' + (ov.published_30d || 0)],
      ['Видео: короткие / длинные', (ov.videos_short || 0) + ' / ' + (ov.videos_long || 0)]
    ].map(function (m) {
      return '<div class="ops-metric"><div class="ops-metric-k">' + esc(m[0])
        + '</div><div class="ops-metric-v">' + m[1] + '</div></div>';
    }).join('');

    var errorsHtml = alerts.length
      ? '<ul class="ops-list">' + alerts.slice(0, 8).map(function (a) {
        return '<li><span class="ops-dot ' + (a.level === 'error' ? 'ops-bad' : 'ops-warnc')
          + '"></span>' + esc(a.text)
          + (a.link ? ' <a href="' + esc(a.link) + '" data-link="' + esc(a.link) + '">открыть</a>' : '')
          + '</li>';
      }).join('') + '</ul>'
      : '<p class="ops-muted">Ошибок нет.</p>';

    var acts = (data && data.activity ? data.activity : []).filter(function (a) {
      return a.type === 'published';
    }).slice(0, 5);
    var pubHtml = acts.length
      ? '<ul class="ops-list">' + acts.map(function (a) {
        return '<li>' + esc((a.at || '').slice(0, 16).replace('T', ' ')) + ' · ' + esc(a.text) + '</li>';
      }).join('') + '</ul>'
      : '<p class="ops-muted">Публикаций пока нет.</p>';

    root.innerHTML =
      '<div class="ops-head">'
      + '<div><h2 style="margin:0;">Operations</h2>'
      + '<p class="ops-muted" style="margin:4px 0 0;">Состояние инфраструктуры и очередей Video Factory. Только реальные данные.</p></div>'
      + '<div class="ops-head-right"><span class="ops-muted" id="opsUpdated">Обновлено: '
      + esc(new Date().toLocaleTimeString()) + '</span>'
      + '<button class="btn btn-secondary" id="opsRefresh" type="button">Обновить</button></div>'
      + '</div>'
      + '<div class="ops-card"><h3>Health</h3><table class="ops-table"><thead><tr>'
      + '<th>Компонент</th><th>Статус</th><th>Детали</th></tr></thead><tbody>'
      + health + '</tbody></table></div>'
      + '<div class="ops-card"><h3>Очереди и задачи</h3><div class="ops-metrics">' + metrics + '</div></div>'
      + '<div class="ops-grid2">'
      + '<div class="ops-card"><h3>Последние ошибки</h3>' + errorsHtml + '</div>'
      + '<div class="ops-card"><h3>Последние публикации</h3>' + pubHtml + '</div>'
      + '</div>';

    var btn = document.getElementById('opsRefresh');
    if (btn) btn.onclick = function () { load(root); };
  }

  function load(root) {
    root.innerHTML = skeleton() + skeleton();
    var out = { data: null, readiness: null };
    get('/api/factory-dashboard')
      .then(function (d) {
        out.data = d;
        return get('/api/readiness').catch(function () { return null; });
      })
      .then(function (r) { out.readiness = r; render(root, out.data, out.readiness, null); })
      .catch(function (e) { render(root, null, null, e); });
  }

  function mount() {
    var root = document.getElementById('operationsRoot');
    if (root && !root.getAttribute('data-ops-mounted')) {
      root.setAttribute('data-ops-mounted', '1');
      load(root);
    }
  }

  window.AutoSocialOperations = { mount: mount, load: load };
  document.addEventListener('DOMContentLoaded', mount);
  // The SPA re-renders without page loads; poll cheaply for the mount point.
  setInterval(function () {
    var root = document.getElementById('operationsRoot');
    if (root && !root.getAttribute('data-ops-mounted')) mount();
  }, 700);
})();
