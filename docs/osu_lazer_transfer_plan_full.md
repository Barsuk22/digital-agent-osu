# План переноса RL-агента osu! в osu!lazer
## Production-oriented technical plan

---

## Текущий статус реализации

Ничего не готово

## 1. Цель проекта

Перенести существующего RL-агента osu! из Python-симулятора в реальный `osu!lazer`, сохранив текущий уровень качества игры на easy-картах и подготовив архитектуру для дальнейшего роста.

### Основные цели

- перенести обученную policy из текущего Python-стека в реальную игровую среду `osu!lazer`;
- обеспечить управление курсором и кликами в реальном времени;
- повторно использовать существующую логику наблюдений, парсинга карт и метрик;
- сохранить поддержку:
  - circle timing,
  - slider follow,
  - spinner control;
- заложить основу для будущей интеграции skill system из `Phase 10–11`.

### Итоговый результат

На выходе должна получиться рабочая система:

```text
osu!lazer <-> external controller <-> policy runtime
```

которая способна:

- читать состояние карты;
- формировать наблюдение формата, совместимого с текущей policy;
- выполнять инференс;
- управлять мышью в реальном времени;
- логировать результаты и сравнивать их с симулятором.

---

## 2. Исходная база проекта

На момент старта уже существует рабочая Python-база, которую нужно не перепридумывать, а переносить и адаптировать.

### Уже реализовано

- `.osu` parser;
- `OsuEnv` с observation/action loop;
- формат наблюдения через `obs_to_numpy()`;
- фиксированный `upcoming_count = 5`;
- support для circles / sliders / spinners;
- replay pipeline;
- eval pipeline;
- phase-based checkpoints;
- метрики качества для timing / slider / spinner;
- skill runtime и skill memory как отдельный слой поверх baseline policy.

### Базовый checkpoint для переноса

Основной рабочий checkpoint:

```text
artifacts/runs/osu_phase8_easy_generalization/checkpoints/best_easy_generalization.pt
```

Именно он должен использоваться как стартовая policy для интеграции в `osu!lazer`.

---

## 3. Архитектурное решение

### 3.1. Главный принцип

На первом рабочем этапе **не нужно одновременно тащить и ONNX, и C# inference, и Python inference**.

Это создаёт лишнюю сложность.

### Правильная последовательность

#### Этап A — first playable integration

- `C#` отвечает за:
  - захват окна;
  - screen capture;
  - синхронизацию;
  - расчёт observation;
  - mouse input.
- `Python` отвечает за:
  - загрузку checkpoint;
  - инференс policy;
  - возврат действия.

Связь между ними:

- `ZeroMQ` или `Named Pipes`.

#### Этап B — optimization / packaging

После того как система уже реально играет в Lazer, можно:

- экспортировать policy в ONNX;
- перенести inference в C#;
- убрать Python из runtime-цикла.

### 3.2. Почему это лучший путь

Такой порядок даёт:

- быстрый первый рабочий результат;
- меньше неизвестных на старте;
- возможность отлаживать только одну новую большую часть за раз;
- полное повторное использование уже существующей PyTorch policy.

---

## 4. Финальная архитектура по этапам

### Первая рабочая архитектура

```text
[osu!lazer]
    ^
    |
screen/input
    |
[C# External Controller]
    |
observation/action IPC
    |
[Python Policy Server]
```

### Поздняя оптимизированная архитектура

```text
[osu!lazer]
    ^
    |
screen/input
    |
[C# External Controller + ONNX Runtime]
```

---

## 5. Ключевые инженерные принципы

1. **Не модифицировать osu!lazer на первом этапе.**  
   Используется внешний контроллер.

2. **Не переносить всё сразу.**  
   Сначала запускаем живой цикл `видим -> думаем -> двигаем`.

3. **Не делать pixel judgement detector обязательным для первого запуска.**  
   Для первых версий он нужен только для диагностики и метрик, но не для базового движения агента.

4. **Максимально переиспользовать существующий Python-код.**  
   Особенно:
   - observation schema;
   - parser semantics;
   - slider path math;
   - normalization logic.

5. **Держать измеримость.**  
   Каждый этап должен иметь конкретные критерии готовности.

---

## 6. Область переноса

### 6.1. Что переносится обязательно

#### Из Python в C# / runtime logic

- `.osu` parsing semantics;
- upcoming object selection;
- slider runtime geometry;
- spinner runtime geometry;
- текущее observation representation;
- action application semantics.

#### Остаётся в Python на первом этапе

- checkpoint loading;
- policy forward pass;
- baseline action generation;
- при необходимости — skill system.

### 6.2. Что пока не является обязательным

На первом минимальном рабочем этапе можно **не переносить полностью**:

- offline reward shaping;
- training loop;
- auto skill extraction;
- advanced eval reporting;
- pixel-based judgement classifier;
- packaging без Python.

---

## 7. Фаза 0 — Аудит и подготовка

**Срок:** 1–2 дня

### Цели

- подтвердить среду запуска;
- уточнить способ привязки ко времени карты;
- подготовить отдельный runtime-контур для `osu!lazer`.

### Задачи

#### 7.1. Аудит osu!lazer

- проверить способ запуска и поведение окна;
- определить, как удобнее всего:
  - найти окно;
  - получить client area;
  - синхронизировать старт карты;
- проверить стабильность fullscreen / borderless / windowed режимов.

#### 7.2. Подготовка инструментов

- установить `.NET 8 SDK`;
- подготовить новый C# проект;
- установить Python runtime зависимости:
  - `torch`
  - `numpy`
  - `pyzmq`
  - позже: `onnx`, `onnxruntime`

#### 7.3. Создание структуры нового компонента

Рекомендуемый отдельный модуль:

```text
external/osu_lazer_controller/
```

или отдельный репозиторий:

```text
OsuLazerController/
```

### Результат фазы

Готовая среда разработки и пустой C# runtime skeleton.

---

## 8. Фаза 1 — Policy runtime bridge

**Срок:** 1 день

### Цель

Поднять Python policy server и стандартизировать IPC между C# и Python.

### Задачи

#### 8.1. Вынести baseline inference в отдельный модуль

Нужен отдельный Python entrypoint, например:

```text
src/apps/serve_osu_policy.py
```

Он должен:

- загружать `best_easy_generalization.pt`;
- строить модель с совместимой размерностью входа;
- принимать observation как массив `float32`;
- возвращать действие:
  - `dx`
  - `dy`
  - `click_strength`

#### 8.2. Зафиксировать IPC контракт

##### Observation payload

```json
{
  "obs": [0.1, 0.2, 0.3]
}
```

##### Action payload

```json
{
  "dx": 0.0,
  "dy": 0.0,
  "click_strength": 0.0
}
```

#### 8.3. Согласовать версию observation schema

Наблюдение должно быть **бит-в-бит совместимо** с текущей логикой `obs_to_numpy()` из проекта. Это критично, потому что именно в таком формате обучалась policy.

### Результат фазы

Python policy server работает отдельно и принимает observation по IPC.

---

## 9. Фаза 2 — Базовый C# контроллер окна и ввода

**Срок:** 2–3 дня

### Цель

Научить C# находить `osu!lazer`, читать его экран и управлять мышью.

### Задачи

#### 9.1. Поиск окна

- поиск окна через WinAPI;
- повторные попытки поиска;
- валидация размеров и состояния окна.

#### 9.2. Screen capture

Реализовать `ScreenCapture`:

- захват клиентской области окна;
- работа в реальном времени;
- кэширование размеров и координат.

#### 9.3. Mouse controller

Реализовать:

- `MoveMouseTo(x, y)`
- `LeftDown()`
- `LeftUp()`
- `Click()`

Лучше через `SendInput`, а не через высокоуровневые обёртки.

#### 9.4. Smoke test

Тестовый режим:

- движение по окружности;
- клик раз в N миллисекунд;
- ручная проверка, что `osu!lazer` реально принимает ввод.

### Результат фазы

C# компонент умеет видеть окно и управлять мышью.

---

## 10. Фаза 3 — Парсинг карты и тайминг

**Срок:** 2–4 дня

### Цель

Научить внешний контроллер понимать, что именно сейчас происходит на карте.

### Задачи

#### 10.1. Порт `.osu` parser

Из Python-парсера переносятся:

- metadata;
- difficulty;
- timing points;
- hit objects;
- slider parameters;
- spinner data.

#### 10.2. Порт базовых доменных моделей

Нужны C# аналоги:

- `Beatmap`
- `HitObject`
- `Circle`
- `Slider`
- `Spinner`
- `TimingPoint`

#### 10.3. Синхронизация времени карты

На первом этапе рекомендуется простой и управляемый вариант:

- пользователь запускает карту;
- контроллер запускает `Stopwatch` по горячей клавише / команде;
- затем считает `current_time_ms`.

Позже можно добавлять:

- auto-start detection;
- screen-based start detection;
- audio offset calibration.

### Результат фазы

Контроллер знает, какая карта играет и какое в ней текущее время.

---

## 11. Фаза 4 — Построение observation

**Срок:** 3–5 дней

### Цель

Собрать observation, идентичный тому, на котором обучалась Python policy.

### Задачи

#### 11.1. Upcoming objects

На каждом шаге нужно строить массив upcoming объектов:

- максимум 5;
- в порядке приоритета;
- с теми же признаками, что и в Python.

#### 11.2. Cursor state

Нужны:

- `cursor_x`
- `cursor_y`

#### 11.3. Slider state

Нужны:

- `active_slider`
- `progress`
- `target_x`
- `target_y`
- `distance_to_target`
- `inside_follow`
- `head_hit`
- `time_to_end_ms`
- `tangent_x`
- `tangent_y`
- `follow_radius`

#### 11.4. Spinner state

Нужны:

- `active_spinner`
- `progress`
- `spins`
- `target_spins`
- `time_to_end_ms`
- `center_x`
- `center_y`
- `distance_to_center`
- `radius_error`
- `angle_sin`
- `angle_cos`
- `angular_velocity`

#### 11.5. Финальная нормализация

Нормализация должна повторять текущую Python-функцию `obs_to_numpy()` без самодеятельности.

### Результат фазы

C# умеет собирать observation-вектор совместимого формата.

---

## 12. Фаза 5 — Slider и spinner runtime port

**Срок:** 3–5 дней

### Цель

Сделать корректную геометрию сложных объектов.

### Задачи

#### 12.1. Slider path port

Перенести математику из `slider_path.py` в C#:

- path sampling;
- `position_at_progress`;
- `tangent_at_progress`.

#### 12.2. Slider runtime state

Нужно корректно вычислять:

- текущую позицию бегунка;
- направление касательной;
- follow radius;
- факт нахождения курсора внутри follow area.

#### 12.3. Spinner runtime state

Нужно вычислять:

- угол курсора вокруг центра;
- изменение угла за шаг;
- скорость вращения;
- накопленный прогресс спиннера.

### Результат фазы

Слайдеры и спиннеры в Lazer runtime описываются так же, как в симуляторе.

---

## 13. Фаза 6 — Первый end-to-end loop

**Срок:** 2–3 дня

### Цель

Запустить полный цикл:

```text
screen/time/map -> observation -> Python policy -> action -> mouse input
```

### Задачи

#### 13.1. Основной игровой цикл

На каждом шаге:

1. взять текущее время карты;
2. построить observation;
3. отправить observation в Python;
4. получить action;
5. применить action;
6. повторить на фиксированном tick rate.

#### 13.2. Частота обновления

Целевой старт:

- `60 Hz` loop;
- допустимый минимум: `50 Hz`.

#### 13.3. Первичная проверка

Проверить, что агент:

- двигается к объектам;
- пытается попадать;
- удерживает слайдеры;
- не ломает управление на спиннерах.

### Результат фазы

Агент реально играет в `osu!lazer`, пусть ещё без идеальной калибровки.

---

## 14. Фаза 7 — Логирование и диагностика

**Срок:** 2–3 дня

### Цель

Сделать систему наблюдаемой, чтобы можно было понимать, почему она играет хуже или лучше, чем в симуляторе.

### Задачи

#### 14.1. Runtime logs

Логировать:

- loop time;
- IPC latency;
- action values;
- cursor position;
- текущий target;
- active slider/spinner state.

#### 14.2. Replay trace

Сохранять runtime trace в JSON-формате, максимально близком к существующему replay pipeline.

#### 14.3. Overlay / debug mode

Опционально:

- отдельное окно;
- текстовая панель;
- отрисовка target point и текущего курсора.

### Результат фазы

Есть инструменты, чтобы сравнивать Lazer runtime и Python simulation.

---

## 15. Фаза 8 — Калибровка тайминга и координат

**Срок:** 2–5 дней

### Цель

Подтянуть реальную игру к качеству симулятора.

### Основные проблемы этой фазы

- задержка screen capture;
- задержка IPC;
- разница между playfield координатами симулятора и Lazer;
- стартовый offset карты;
- разница в кликовом поведении реальной игры.

### Задачи

#### 15.1. Coordinate mapping

Нужно точно сопоставить:

- playfield `512x384`
- экранные координаты окна Lazer

#### 15.2. Time offset calibration

Ввести конфиг:

- `audio_offset_ms`
- `input_delay_ms`
- `capture_delay_ms`

#### 15.3. Click threshold tuning

Подобрать:

- `click threshold`
- `slider hold threshold`
- `spinner hold threshold`

### Результат фазы

Агент играет заметно ближе к offline eval.

---

## 16. Фаза 9 — Runtime evaluation against simulator

**Срок:** 2–3 дня

### Цель

Сравнить реальный `osu!lazer` runtime с симулятором.

### Метрики

Сравнивать по картам из current easy pool:

- hit rate;
- miss count;
- slider inside ratio;
- slider follow distance mean;
- slider finish rate;
- spinner clear / partial / miss;
- loop FPS;
- runtime stability.

### Критерий приемки

Допустимое отклонение от симулятора:

- не более `5–10%` на простых easy-картах;
- без критических провалов на слайдерах и спиннерах.

### Результат фазы

Подтверждён первый боевой перенос policy в реальную игру.

---

## 17. Фаза 10 — Pixel judgement detector (опционально, но полезно)

**Срок:** 2–5 дней

### Цель

Добавить внешний детект результатов попаданий для более точной аналитики.

### Важно

Это не блокер первого playable milestone.

### Что даёт

- сравнение timing windows;
- подтверждение попаданий;
- внешнюю валидацию результата;
- дополнительный runtime debug.

### Реализация

- локальный screen region capture;
- template matching / simple CV;
- позже — более умный detector.

### Результат фазы

Появляется более точный внешний eval слой.

---

## 18. Фаза 11 — ONNX export и перенос inference в C#

**Срок:** 2–4 дня

### Цель

Убрать Python из runtime-цикла после того, как всё уже работает.

### Задачи

#### 18.1. Экспорт модели в ONNX

- загрузка `best_easy_generalization.pt`;
- экспорт policy в `.onnx`;
- batch dynamic axis;
- проверка численной близости.

#### 18.2. ONNX Runtime integration

- загрузка модели в C#;
- inference по текущему observation;
- проверка совпадения action с Python baseline.

#### 18.3. Замена Python policy server

Переключение режима:

- `python_runtime`
- `onnx_runtime`

### Результат фазы

Получаем более компактную и быструю production-версию.

---

## 19. Фаза 12 — Подключение skill system

**Срок:** после стабилизации базового runtime

### Цель

Добавить `Phase 10–11 skill layer` поверх baseline агента уже в реальном runtime.

### Принцип

Skill system не должен заменять policy.  
Он должен оставаться:

- assist layer;
- bounded local bias;
- optional runtime enhancement.

### Задачи

- определить, живёт ли skill runtime в Python или переносится отдельно;
- сначала включать только в debug/experimental режиме;
- сравнивать:
  - baseline only
  - baseline + skill system

### Результат фазы

Реальный Lazer runtime получает расширяемую skill-aware архитектуру.

---

## 20. Фаза 13 — Packaging и deployment

**Срок:** 1–3 дня

### Цель

Подготовить перенос в форму, удобную для повседневного запуска и распространения: `.exe`, embedded runtime, bat-скрипт, конфиги и документация.

### Подход

Здесь есть **два варианта развёртывания**, и их нужно держать отдельно.

---

### 20.1. Вариант A — First usable build (Python остаётся в runtime)

Это первый нормальный способ запустить систему как почти готовый продукт, не вырезая Python из архитектуры.

#### Состав сборки

- `OsuLazerController.exe`
- Python runtime
- checkpoint или ONNX-модель
- `agent_server.py`
- launch script
- конфиги
- документация

#### Предлагаемая структура папок

```text
release/
  OsuLazerController.exe
  start_agent.bat
  configs/
    runtime.json
  model/
    best_easy_generalization.pt
    best_easy_generalization.onnx
  runtime/
    python.exe
    python39.dll
    Lib/
    site-packages/
  python/
    agent_server.py
    serve_osu_policy.py
  logs/
  docs/
```

---

### 20.2. Сборка C# приложения

Опубликовать как однофайловое приложение:

```powershell
dotnet publish -c Release -r win-x64 -p:PublishSingleFile=true --self-contained true
```

или, если нужен более лёгкий вариант:

```powershell
dotnet publish -c Release -r win-x64 -p:PublishSingleFile=true
```

#### Что должно войти в сборку

- основной controller;
- зависимости, необходимые для:
  - ONNX Runtime;
  - OpenCvSharp;
  - ZeroMQ / NetMQ;
  - вспомогательных runtime-библиотек.

#### Что проверить после publish

- запускается ли `.exe` без Visual Studio;
- не теряются ли native зависимости;
- корректно ли работает `SendInput`;
- не ломается ли screen capture на целевой машине.

---

### 20.3. Включение Python runtime

Если используется вариант с Python policy server, нужно приложить embedded Python.

#### Минимальный состав

- `python.exe`
- `python39.dll` или версия, соответствующая выбранному runtime
- стандартная библиотека Python
- зависимости проекта

#### Что должно лежать рядом

- `agent_server.py`
- `serve_osu_policy.py`
- `best_easy_generalization.pt` **или**
- `best_easy_generalization.onnx`
- необходимые Python-пакеты:
  - `numpy`
  - `pyzmq`
  - при необходимости `onnxruntime`

#### Важное замечание

Если инференс уже полностью перенесён в C#, embedded Python больше не нужен.  
Но до этого момента он остаётся самым простым путём для first usable build.

---

### 20.4. Скрипт запуска

Нужен единый стартовый файл, например:

```batch
@echo off
start /B runtime\python.exe python\agent_server.py
timeout /t 2 > nul
OsuLazerController.exe --map "Spica"
```

#### Что ещё нужно предусмотреть

- остановку Python-процесса при закрытии контроллера;
- обработку ситуации, если Python server не поднялся;
- логирование ошибок старта;
- отдельный код возврата при неуспешном запуске.

---

### 20.5. Вариант B — Optimized build (без Python в runtime)

После переноса policy в ONNX и ONNX Runtime можно сделать более чистую production-сборку.

#### Состав сборки

- `OsuLazerController.exe`
- `.onnx` модель
- конфиги
- документация
- при необходимости debug tools

#### Структура

```text
release/
  OsuLazerController.exe
  start_agent.bat
  configs/
    runtime.json
  model/
    best_easy_generalization.onnx
  logs/
  docs/
```

#### Плюсы

- меньше внешних зависимостей;
- проще запуск;
- меньше точек отказа;
- удобнее переносить между машинами.

---

### 20.6. Документация к развёртыванию

Обязательные элементы:

- `README` для запуска;
- `docs/deployment.md`;
- `docs/configuration.md`;
- `docs/troubleshooting.md`.

#### Что должно быть описано

- как запустить агент;
- где лежит модель;
- как выбрать карту;
- как указать режим работы:
  - Python runtime;
  - ONNX runtime;
- как включить debug;
- как посмотреть логи;
- что делать, если не найдено окно `osu!lazer`.

### Результат фазы

Готовая сборка, которую можно запускать одной командой или через `.bat`, а в поздней версии — как самостоятельный `.exe`-runtime.

---

## 21. Критерии успеха

Система считается успешно перенесённой, если:

### Функционально

- агент стабильно запускается рядом с `osu!lazer`;
- корректно строит observation;
- управляет мышью без зависаний;
- проходит карту целиком.

### По качеству игры

На easy/generalization картах целевые ориентиры:

- `hit rate >= 0.95`
- `slider inside ratio >= 0.95`
- `slider follow distance <= 40 px`
- `spinner clear/partial >= 0.80`

### По runtime

- `>= 50 FPS` эффективного control loop;
- отсутствие крашей;
- отсутствие desync, разрушающего прохождение карты.

---

## 22. Рекомендуемый порядок реализации

### Порядок без ошибок и лишней боли

1. подготовка среды;
2. Python policy server;
3. C# window/input layer;
4. parser + timing;
5. observation builder;
6. slider/spinner runtime;
7. first end-to-end play;
8. logging + calibration;
9. runtime eval;
10. ONNX optimization;
11. skill system integration;
12. packaging.

---

## 23. Что НЕ нужно делать слишком рано

Не рекомендуется на старте:

- сразу делать ONNX-only architecture;
- сразу пытаться читать память процесса;
- сразу делать GUI launcher;
- сразу тащить skill system в первый живой запуск;
- сразу делать идеальный detector judgement по пикселям.

Сначала нужен живой и стабильный базовый loop.

---

## 24. Финальная схема

### Стартовая рабочая версия

```text
[osu!lazer]
   ^
   |
screen capture + input
   |
[C# External Controller]
   |
ZeroMQ / IPC
   |
[Python Policy Server]
```

### Финальная production-версия

```text
[osu!lazer]
   ^
   |
screen capture + input
   |
[C# Controller + ONNX Runtime]
```

### Расширенная future-версия

```text
[osu!lazer]
   ^
   |
[C# Runtime Controller]
   |
[Baseline Policy]
   |
[Optional Skill Layer]
```

---

## 25. Итог

Этот перенос — не просто “запустить бота в другой игре”.

Это переход от:

- offline симулятора;
- контролируемой среды;
- удобного eval pipeline

к:

- реальному времени;
- реальному окну;
- реальному вводу;
- реальным системным задержкам.

Поэтому правильная цель первой большой победы звучит так:

> не “сразу идеально production-ready”,  
> а “агент в реальном osu!lazer повторяет свою симуляторную логику и реально играет карту”.

После этого уже можно:

- допиливать точность;
- ускорять runtime;
- убирать Python;
- добавлять skill system;
- строить полноценную боевую внешнюю интеграцию.
