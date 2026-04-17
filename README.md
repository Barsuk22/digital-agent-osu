# 🎮 Digital Agent OSU

> AI-агент, который учится играть в osu! **самостоятельно**, через reinforcement learning

---

## 🚀 Demo

*(сюда потом вставишь gif)*

```
assets/demo.gif
```

---

## 🧠 Что это такое

Это не бот со скриптами.
Это агент, который:

* видит карту
* двигает курсор
* кликает
* получает reward
* **учится играть сам**

---

## 🧩 Архитектура

```
input (map)
   ↓
environment (osu world)
   ↓
agent (policy)
   ↓
action (dx, dy, click)
   ↓
judgement (300 / 100 / miss)
   ↓
reward
   ↓
learning
```

---

## 🏗️ Структура проекта

```
src/
 ├── skills/osu/      # вся логика osu
 ├── learning/        # RL обучение
 ├── girl/            # будущий character brain
 ├── agent/           # execution слой
```

---

## 🎯 Текущий статус

### ✅ Phase 0 — Foundation (ЗАВЕРШЕНА)

Система уже умеет:

* парсить `.osu` карты
* рассчитывать timing (AR / OD)
* обрабатывать:

  * circles
  * sliders
  * spinners
* считать попадания:

  * 300 / 100 / 50 / miss
* запускать live viewer
* записывать replay

---

## 🎮 Viewer

Реализовано:

* курсор с хвостом
* клики (анимация)
* hit bursts (300/100/50)
* combo / accuracy
* sliders (с follow circle)
* replay

---

## ⚙️ Запуск

### ▶ Live (агент играет)

```bash
python -m src.apps.live_viewer_osu
```

---

### ▶ Replay

```bash
python -m src.apps.replay_osu
```

---

## 📊 Обучение

Агент обучается через RL:

* движение к объектам
* клик в нужное время
* уменьшение случайных действий

---

## 🛣️ Roadmap

### Phase 1 — Initial Contact

* агент перестаёт кликать в пустоту
* начинает попадать

### Phase 2 — Timing

* учится нажимать вовремя

### Phase 3 — Aim

* связывает позицию и клик

### Phase 4+ — Skills

* sliders
* patterns
* skill memory

---

## ⚠️ Важно

В репозитории **нет карт и аудио**.

Добавь свои `.osu` карты сюда:

```
data/raw/osu/maps/
```

---

## 🔮 Дальше

План:

* обучение на реальных картах
* multi-map generalization
* skill extraction
* интеграция с AI персонажем

---

## 💙 Идея проекта

Цель — не просто сделать агента,
а построить систему, которая:

* учится
* запоминает
* формирует навыки

И потом становится частью **цифровой личности**.

---
