# OSU Environment Specification

## Общая идея

Environment — это "игровой мир", в котором живёт агент.

Он получает состояние (observation) и делает действие (action).

---

## Observation

Содержит:

* `time_ms`
* `cursor_x`, `cursor_y`
* список `upcoming` объектов

Каждый объект:

* тип (circle / slider / spinner)
* позиция
* время до попадания
* расстояние до курсора
* активность

---

## Action

```
dx, dy — движение
click_strength — сила клика
```

Клик считается активным, если:

```
click_strength >= threshold
```

---

## Время

* шаг: ~16.6 ms (60 FPS)
* время идёт независимо от агента

---

## Видимые объекты

Объекты появляются заранее (AR → preempt time)

---

## Завершение эпизода

Когда:

* все объекты обработаны
* нет активных slider/spinner

---

## Replay

Каждый шаг сохраняется:

* позиция курсора
* клик
* judgement
* reward

---
