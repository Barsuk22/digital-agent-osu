# Phase 1 / Initial Learning / Base PPO Learning — статус

Статус: закрыта по смыслу как этап достижения базовой обучаемости.

Phase 1 была стадией, где агент должен был перестать быть просто средой с viewer и начать реально обучаться через PPO. По текущему состоянию кода этот рубеж пройден.

## Что уже есть

- PPO training loop в `src/apps/train_osu.py`;
- Actor-Critic model на PyTorch;
- continuous action space: `dx`, `dy`, `click_strength`;
- rollout по настоящей `.osu` карте;
- GAE и PPO update;
- reward shaping поверх environment reward;
- сбор метрик по reward, hit rate, clicks, useful clicks, idle, jerk, overspeed, flow;
- сохранение checkpoints;
- загрузка базового checkpoint для продолжения обучения;
- eval pipeline через deterministic policy;
- replay после eval.

## Почему Phase 1 считается закрытой

Phase 1 не требовала идеальной игры. Её смыслом было доказать, что агент:

- реально проходит цикл обучения;
- двигается по карте;
- взаимодействует с объектами;
- получает meaningful reward;
- способен попадать;
- сохраняет и загружает состояние обучения;
- может быть проверен через eval/replay.

Эти свойства в проекте уже присутствуют.

## Что не считается закрытым

Закрытие Phase 1 не означает, что агент стабилен на любых картах или играет на высоком уровне. Не закрыты:

- устойчивое multi-map обобщение;
- полноценная slider-игра на уровне osu!;
- сложные паттерны;
- стабильная высокая accuracy;
- skill extraction и skill memory.

## Текущий переход

Текущая ветка обучения фактически является Phase 1.5: fine-tuning качества движения.

В коде это видно по:

- отдельным checkpoint-файлам `best_recoil.pt` и `latest_recoil.pt`;
- загрузке базового `best.pt` / `latest.pt`;
- anti-recoil reward shaping;
- penalty за jerk и overspeed;
- flow reward после hit;
- удержанию отдельного `best_reward` для fine-tune ветки.

Основная работа теперь: не «научить вообще играть», а сделать поведение более качественным, плавным и человекоподобным.
