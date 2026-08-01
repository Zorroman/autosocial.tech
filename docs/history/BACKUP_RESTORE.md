# Backup & Restore (AutoSocial YouTube Factory)

## Что сохранять
| Данные | Где | Критичность |
|---|---|---|
| База данных | `autosocial.db` (dev) / PostgreSQL dump (prod) | критично: каналы, проекты, сцены, публикации, аналитика, расходы, зашифрованные OAuth-токены |
| `.env` | корень проекта на сервере | критично: все ключи, включая `TOKEN_ENCRYPTION_KEY` |
| Готовые видео | `BASE_DIR/output/videos/` | важно (можно перерендерить, но дорого по времени) |
| Voiceover | `BASE_DIR/output/audio/` | желательно |
| Загруженные/стоковые медиа | `BASE_DIR/cache/footage/` | опционально (скачиваются заново) |

Никогда не кладите бэкапы с секретами в git.

## Backup
```bash
# SQLite (остановив запись или через .backup):
sqlite3 autosocial.db ".backup backup/autosocial_$(date +%Y%m%d).db"
cp .env backup/env_$(date +%Y%m%d)          # хранить вне git, с правами 600
tar czf backup/output_$(date +%Y%m%d).tgz output/videos output/audio
```
PostgreSQL: `pg_dump "$DATABASE_URL" > backup/db_$(date +%Y%m%d).sql`.

## Restore
1. Остановить web и worker.
2. Вернуть файл БД / `psql < dump`.
3. Вернуть `.env` (тот же `TOKEN_ENCRYPTION_KEY`!).
4. Вернуть `output/` при необходимости.
5. Запустить web → миграции применятся автоматически.
6. Проверка restore: `GET /api/health` → 200; логин админа; `/channels/`
   показывает каналы; `GET /api/readiness` → ready/degraded; открыть один
   готовый MP4 через «Видео-проекты».

## Потеря TOKEN_ENCRYPTION_KEY
Зашифрованные OAuth-токены (YouTube/Meta) станут нерасшифруемыми навсегда.
Приложение продолжит работать, но все подключения придётся выполнить заново
(«Переподключить» в Каналы → YouTube). Сами каналы, проекты, видео и
аналитика не пострадают. Поэтому ключ бэкапится вместе с БД, отдельно от git.
