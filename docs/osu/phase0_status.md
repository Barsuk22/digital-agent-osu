Phase 0 — Core Foundation (Status)
Цель

Создать честную osu-like среду, где агент действительно играет, а не симулирует.

Что реализовано
Parser
чтение .osu
circles / sliders / spinners
timing points
difficulty (CS, OD, AR)
Environment
время (time_ms)
курсор (cursor_x, cursor_y)
upcoming objects
distance / timing до цели
Action space
dx, dy — движение
click_strength — клик
Hit system
300 / 100 / 50 / miss
проверка радиуса
timing окна (OD)
Sliders
head hit
follow логика
ticks (базово)
завершение
Spinner
вращение через изменение угла
накопление прогресса
оценка по количеству оборотов
Viewer (pygame)
отображение карты
курсор с хвостом
клики
эффекты попаданий
combo / accuracy
replay
Что упрощено
slider path не идеально соответствует osu (особенно passthrough)
follow circle упрощён
нет полной точности lazer renderer
нет input lag модели
нет human-like ограничений
Итог

Среда:
✔ честная
✔ замкнутая
✔ подходит для RL

Агент:
✔ может действовать
✔ получает reward
❗ пока действует хаотично

Следующий шаг

👉 Phase 1 — Initial Contact

Задача:

научить агента вообще взаимодействовать с объектами