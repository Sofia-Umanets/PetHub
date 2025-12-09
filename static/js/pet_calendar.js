document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendar');
    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'ru',
        height: 'auto',
        events: calendarEvents,
        dateClick: function(info) {
            const clickedDate = info.dateStr;
            document.getElementById('eventDate').innerText = clickedDate;

            const matched = calendar.getEvents().filter(e => e.startStr === clickedDate);
            let html = '';

            if (matched.length > 0) {
                matched.forEach(event => {
                    const yearlyNote = event.extendedProps.is_yearly ? ' (Ежегодное)' : '';
                    const statusClass = event.extendedProps.is_done ? 'done' : 'not-done';
                    html += `
                        <div class="event-card ${statusClass}">
                            <b>${event.title} - ${event.startStr}${yearlyNote}</b><br>
                            ${event.extendedProps.time ? `Время: ${event.extendedProps.time}<br>` : ''}
                            ${event.extendedProps.note ? `Заметка: ${event.extendedProps.note}<br>` : ''}
                            ${event.extendedProps.remind ? `<i>Напомнить: ${event.extendedProps.remind}</i><br>` : ''}
                            ${event.extendedProps.is_done ? '✅ Выполнено' : '❌ Не выполнено'}<br>
                            <div class="event-actions">
                                <a href="${event.extendedProps.edit_url}" class="btn">✏️ Редактировать</a>
                                ${!event.extendedProps.is_done ? 
                                    `<a href="${event.extendedProps.done_url}" class="btn" 
                                        onclick="return confirm('Отметить событие как выполненное?')">
                                        ✅ Завершить
                                    </a>` 
                                    : ''
                                }
                                <form action="${event.extendedProps.delete_url}" method="post" onsubmit="return confirm('Удалить событие?')">
                                    <input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken}">
                                    <button type="submit" class="btn">🗑 Удалить</button>
                                    <label for="id_delete_all">
                                        <input type="checkbox" id="id_delete_all" name="delete_all">
                                        Удалить все события с этим названием
                                    </label>
                                </form>
                            </div>
                        </div><br>`;
                });
            } else {
                html = '<p>Нет событий</p>';
            }

            document.getElementById('eventList').innerHTML = html;
            document.getElementById('eventModal').style.display = 'block';
        }
    });

    calendar.render();

    // Обработка якоря в URL
    if (window.location.hash) {
        const dateStr = window.location.hash.slice(1);
        try {
            const date = new Date(dateStr);
            if (!isNaN(date)) {
                calendar.gotoDate(date);
                
                setTimeout(() => {
                    const calendarTop = calendarEl.getBoundingClientRect().top;
                    const offset = window.pageYOffset + calendarTop - 100;
                    window.scrollTo({
                        top: offset,
                        behavior: 'smooth'
                    });
                }, 100);
            }
        } catch (e) {
            console.error('Invalid date in hash:', e);
        }
    }
});

function closeModal() {
    document.getElementById('eventModal').style.display = 'none';
}