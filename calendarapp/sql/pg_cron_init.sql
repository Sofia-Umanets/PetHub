CREATE OR REPLACE FUNCTION create_next_year_yearly_events()
RETURNS VOID AS $$
BEGIN
    -- Находим все прошедшие ежегодные события, которые нужно обработать
    WITH passed_yearly_events AS (
        SELECT 
            e1.id AS original_event_id,      -- ID исходного события
            e1.pet_id,                      -- ID питомца
            e1.title,                       -- Название события
            e1.event_type,                  -- Тип события
            e1."date" AS original_date,     -- Дата прошедшего события
            e1.time,                        -- Время события
            e1.duration_minutes,            -- Длительность события
            e1.note                         -- Заметка к событию
        FROM calendarapp_event e1
        WHERE 
            e1.is_yearly = TRUE             -- События должны быть ежегодными
            AND e1."date" < CURRENT_DATE    -- Дата события уже прошла
    ),
    -- Считаем количество будущих событий для каждой комбинации "питомец + название события"
    future_yearly_events AS (
        SELECT 
            e2.pet_id,                      -- ID питомца
            e2.title,                       -- Название события
            COUNT(*) AS future_events_count -- Количество будущих событий
        FROM calendarapp_event e2
        WHERE 
            e2.is_yearly = TRUE             -- События должны быть ежегодными
            AND e2."date" >= CURRENT_DATE   -- Дата события в будущем или сегодня
        GROUP BY e2.pet_id, e2.title
    ),
    -- Выбираем события, для которых нужно создать недостающие будущие события
    events_to_process AS (
        SELECT 
            pye.original_event_id,          -- ID исходного события
            pye.pet_id,                     -- ID питомца
            pye.title,                      -- Название события
            pye.event_type,                 -- Тип события
            pye.original_date,              -- Дата прошедшего события
            pye.time,                       -- Время события
            pye.duration_minutes,           -- Длительность события
            pye.note,                       -- Заметка к событию
            COALESCE(fye.future_events_count, 0) AS existing_future_count -- Количество уже существующих будущих событий
        FROM passed_yearly_events pye
        LEFT JOIN future_yearly_events fye
        ON pye.pet_id = fye.pet_id AND pye.title = fye.title
    ),
    -- Генерируем недостающие будущие события для каждой комбинации "питомец + название события"
    required_future_events AS (
        SELECT 
            etp.original_event_id,          -- ID исходного события
            etp.pet_id,                     -- ID питомца
            etp.title,                      -- Название события
            etp.event_type,                 -- Тип события
            etp.time,                       -- Время события
            etp.duration_minutes,           -- Длительность события
            etp.note,                       -- Заметка к событию
            etp.original_date + (i * INTERVAL '1 year') AS next_year_date -- Дата будущего события
        FROM events_to_process etp
        CROSS JOIN generate_series(1, 3) AS i -- Генерируем серии для 1-го, 2-го и 3-го года
        WHERE i > COALESCE(etp.existing_future_count, 0) -- Создаём только недостающие события
    ),
    -- Вставляем недостающие события в таблицу и получаем их ID
    inserted_events AS (
        INSERT INTO calendarapp_event (
            id,                            -- Уникальный идентификатор события
            pet_id,                        -- ID питомца
            title,                         -- Название события
            event_type,                    -- Тип события
            "date",                        -- Дата будущего события
            time,                          -- Время события
            duration_minutes,              -- Длительность события
            note,                          -- Заметка к событию
            is_yearly,                     -- Признак ежегодного события
            is_done,                       -- Признак выполненного события
            is_event_passed,               -- Признак прошедшего события
            original_event_id              -- Ссылка на исходное событие
        )
        SELECT 
            gen_random_uuid(),             -- Генерируем уникальный идентификатор для нового события
            pet_id,                        -- ID питомца
            title,                         -- Название события
            event_type,                    -- Тип события
            next_year_date,                -- Дата будущего события
            time,                          -- Время события
            duration_minutes,              -- Длительность события
            note,                          -- Заметка к событию
            TRUE,                          -- Событие является ежегодным
            FALSE,                         -- Событие не выполнено
            FALSE,                         -- Событие ещё не прошло
            original_event_id              -- Ссылка на исходное событие
        FROM required_future_events
        ON CONFLICT DO NOTHING
        RETURNING id, original_event_id  -- Возвращаем ID нового события и исходного события
    )

    -- Копируем напоминания для новых событий
    INSERT INTO calendarapp_remindersettings ( -- Исправлено имя таблицы
        event_id,                         -- Новое событие
        pet_id,                           -- ID питомца
        remind_at,                        -- Время напоминания
        repeat,                           -- Повторение
        repeat_days,                      -- Дни повторения
        repeat_every,                     -- Частота повторения
        remind_date,                      -- Дата напоминания
        last_reminded                     -- Последнее напоминание
    )
    SELECT 
        ie.id,                            -- ID нового события
        r.pet_id,                         -- ID питомца
        r.remind_at,                      -- Время напоминания
        r.repeat,                         -- Повторение
        r.repeat_days,                    -- Дни повторения
        r.repeat_every,                   -- Частота повторения
        r.remind_date,                    -- Дата напоминания
        r.last_reminded                   -- Последнее напоминание
    FROM inserted_events ie
    JOIN calendarapp_remindersettings r  -- Исправлено имя таблицы
    ON ie.original_event_id = r.event_id; -- Копируем напоминания для новых событий
END;
$$ LANGUAGE plpgsql;
