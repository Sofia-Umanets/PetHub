CREATE OR REPLACE FUNCTION create_next_year_yearly_events()
RETURNS VOID AS $$
DECLARE
    rec RECORD;
BEGIN
    WITH 
    passed_yearly_events AS (
        SELECT 
            e1.id AS original_event_id,
            e1.pet_id,
            e1.title,
            e1.event_type,
            e1."date" AS original_date,
            e1.time,
            e1.duration_minutes,
            e1.note,
            EXTRACT(YEAR FROM e1."date")::int AS event_year
        FROM calendarapp_event e1
        WHERE e1.is_yearly = TRUE
          AND e1."date" < CURRENT_DATE
    ),
    future_yearly_events AS (
        SELECT 
            e2.pet_id,
            e2.title,
            COUNT(*) AS future_events_count
        FROM calendarapp_event e2
        WHERE e2.is_yearly = TRUE
          AND e2."date" >= CURRENT_DATE
        GROUP BY e2.pet_id, e2.title
    ),
    events_to_process AS (
        SELECT 
            pye.original_event_id,
            pye.pet_id,
            pye.title,
            pye.event_type,
            pye.original_date,
            pye.time,
            pye.duration_minutes,
            pye.note,
            pye.event_year,
            COALESCE(fye.future_events_count, 0) AS existing_future_count
        FROM passed_yearly_events pye
        LEFT JOIN future_yearly_events fye ON pye.pet_id = fye.pet_id AND pye.title = fye.title
    ),
    required_future_events AS (
        SELECT 
            etp.original_event_id,
            etp.pet_id,
            etp.title,
            etp.event_type,
            etp.time,
            etp.duration_minutes,
            etp.note,
            etp.original_date + (i * INTERVAL '1 year') AS next_year_date
        FROM events_to_process etp
        CROSS JOIN generate_series(1, 3) AS i
        WHERE i > COALESCE(etp.existing_future_count, 0)
    ),
    inserted_events AS (
        INSERT INTO calendarapp_event (
            id,
            pet_id,
            title,
            event_type,
            "date",
            time,
            duration_minutes,
            note,
            is_yearly,
            is_done,
            is_event_passed,
            original_event_id
        )
        SELECT
            gen_random_uuid(),
            pet_id,
            title,
            event_type,
            next_year_date,
            time,
            duration_minutes,
            note,
            TRUE,
            FALSE,
            FALSE,
            original_event_id
        FROM required_future_events
        ON CONFLICT DO NOTHING
        RETURNING id, original_event_id, "date"
    )
    INSERT INTO calendarapp_remindersettings (
        event_id,
        pet_id,
        remind_at,
        repeat,
        repeat_days,
        repeat_every,
        remind_date,
        last_reminded
    )
    SELECT 
        ie.id,
        r.pet_id,
        r.remind_at,
        r.repeat,
        r.repeat_days,
        r.repeat_every,
        make_date(
            EXTRACT(YEAR FROM ie."date")::int,
            COALESCE(EXTRACT(MONTH FROM r.remind_date), 1)::int,
            COALESCE(EXTRACT(DAY FROM r.remind_date), 1)::int
        ),
        r.last_reminded
    FROM inserted_events ie
    JOIN passed_yearly_events pye ON ie.original_event_id = pye.original_event_id
    JOIN calendarapp_remindersettings r ON ie.original_event_id = r.event_id;

END;
$$ LANGUAGE plpgsql;



