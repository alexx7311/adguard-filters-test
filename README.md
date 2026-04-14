# AdGuard Filters Update Test Infrastructure

Тестовый фильтр + diff-патчи для полуавтоматической проверки обновления фильтров в AG Mini (AdGuard for Safari).

Покрывает три тест-кейса Allure:
- **TC 10090** — Diff-обновление (инкрементальные патчи)
- **TC 10091** — Полное обновление (скачивание фильтра целиком)
- **TC 10277** — Diff-обновление, затем полное обновление

## Структура репозитория

```
extension/safari/
  filters.json                              # Полная мета фильтров (84 фильтра, как на проде)
  filters_i18n.json                         # Локализации фильтров (копия с прода)
  filters/2_optimized.txt                   # Последняя версия фильтра (v1.0.49)
  patches/2_optimized/                      # 49 RCS diff-патчей + 1 пустой терминальный
base/
  2_optimized_v1.0.0.txt                    # Базовая версия фильтра (v1.0.0, для инъекции в БД)
devconfig/
  devconfig_tc10090.json                    # diff update: timer=25s, diff_period=60s
  devconfig_tc10091.json                    # full update: timer=25s, full_period=60s
  devconfig_tc10277.json                    # diff + full: timer=25s, diff=60s, full=90s
scripts/
  prepare_db.py                             # Подготовка БД для каждого TC
  install_devconfig.sh                      # Установка devConfig (macOS, требует sudo)
  verify_db.py                              # Просмотр состояния БД после теста
```

## Требования

- macOS с установленным AG Mini (AdGuard for Safari)
- Python 3 (только стандартная библиотека)
- Proxyman или Charles для мониторинга сетевых запросов
- `sudo` для установки devConfig

## Быстрый старт

```bash
git clone git@github.com:alexx7311/adguard-filters-test.git
cd adguard-filters-test
```

## TC 10090 — Diff-обновление

Проверяет, что AG Mini применяет diff-патчи (инкрементальное обновление).

### Подготовка

```bash
# 1. Закрой AG Mini

# 2. Подготовь БД и установи в AG Mini (автоматически берёт текущую БД приложения)
python3 scripts/prepare_db.py tc10090 --install

# 3. Установи devConfig (потребуется пароль для sudo)
./scripts/install_devconfig.sh tc10090
```

### Проверка

1. Открой Proxyman, начни запись
2. Запусти AG Mini
3. В настройках включи **AdGuard Base Filter** (фильтр ID 2)
4. Подожди ~60 секунд (diff update cycle)

### Ожидаемый результат

- **Proxyman**: запросы к `raw.githubusercontent.com` за `.patch` файлами (до 49 штук). **НЕ** должно быть запроса к `2_optimized.txt`
- **БД**: версия фильтра изменилась с `1.0.0` на `1.0.49`, количество правил выросло с 20 до 69

```bash
python3 scripts/verify_db.py
```

## TC 10091 — Полное обновление

Проверяет, что AG Mini скачивает фильтр целиком (не через diff).

### Подготовка

```bash
# 1. Закрой AG Mini

# 2. Подготовь БД из результата TC 10090
python3 scripts/prepare_db.py tc10091 --source prepared_dbs/agflm_tc10090.db --install

# 3. Установи devConfig
./scripts/install_devconfig.sh tc10091
```

> Скрипт ставит `last_download_time` на 6 дней назад (фильтр просрочен при `expires=5 дней`) и `next_check_time` в будущее (diff заблокирован) → FLM выбирает полное обновление.

### Проверка

1. Открой Proxyman, начни запись
2. Запусти AG Mini
3. Подожди ~60 секунд (full update cycle)

### Ожидаемый результат

- **Proxyman**: запрос к `2_optimized.txt` (полный фильтр). **НЕ** должно быть запросов к `.patch` файлам
- **БД**: версия `1.0.49`, `rules_text` содержит полный фильтр

## TC 10277 — Diff + Full обновление

Проверяет оба типа обновлений последовательно.

### Подготовка

```bash
# 1. Закрой AG Mini

# 2. Подготовь БД из результата TC 10090
python3 scripts/prepare_db.py tc10277 --source prepared_dbs/agflm_tc10090.db --install

# 3. Установи devConfig
./scripts/install_devconfig.sh tc10277
```

### Проверка

1. Открой Proxyman, начни запись
2. Запусти AG Mini, включи **AdGuard Base Filter**
3. Подожди: сначала ~60с (diff), затем ~90с (full)

### Ожидаемый результат

- **Proxyman**: сначала запросы к `.patch` файлам (diff), затем к `2_optimized.txt` (full)
- **БД**: версия `1.0.49`

## Как это работает

1. **devConfig** перенаправляет `filters_meta_url` и `filters_i18n_url` на этот GitHub-репо
2. **`prepare_db.py`** устанавливает фильтр ID 2 в версию `1.0.0`, `download_url` → GitHub, `is_enabled=0`
3. FLM строит пути к патчам относительно `download_url` → все патчи загружаются с GitHub
4. Цепочка: v1.0.0 → 49 diff-патчей → v1.0.49 (пустой терминальный патч = «обновлений больше нет»)

### Ключевые детали

| Параметр | Значение |
|----------|----------|
| `filters.json` | Полная копия с прода (84 фильтра), только у фильтра 2 изменён `downloadUrl` |
| `filters_i18n.json` | Полная копия с прода (локализации). Без неё `pull_metadata` стирает локализации → «undefined» в UI |
| `is_enabled` | `0` при подготовке БД. AG Mini при запуске принудительно обновляет включённые фильтры — если поставить `1`, тест сломается |
| `rules_text` | Хранится **с trailing newline** (как FLM загружает с сервера). SHA-1 в патчах рассчитан с учётом `\n` |
| `text_hash` | `NULL` в подготовленных БД (FLM не проверяет его перед патчингом) |

## Справка по скриптам

### prepare_db.py

```
python3 scripts/prepare_db.py <tc> [--source <path>] [--install]
```

- `<tc>` — `tc10090`, `tc10091` или `tc10277`
- `--source` — путь к исходной БД (по умолчанию: БД AG Mini)
- `--install` — скопировать подготовленную БД обратно в AG Mini

Скрипт **никогда** не модифицирует исходную БД — всегда работает с копией в `prepared_dbs/`.

### install_devconfig.sh

```
./scripts/install_devconfig.sh <tc>
```

Копирует devConfig в `/Library/Application Support/AdGuard Software/com.adguard.safari.AdGuard/devConfig.json` с `sudo chmod 444 && sudo chown 0:0`.

### verify_db.py

```
python3 scripts/verify_db.py [path_to_db]
```

Читает БД в режиме read-only, показывает состояние фильтра ID 2: версию, `rules_count`, `last_download_time`, `diff_updates`.
