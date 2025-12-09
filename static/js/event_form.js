document.addEventListener("DOMContentLoaded", function() {
    // Функционал для редактирования профиля
    const avatarInput = document.getElementById('id_avatar');
    const avatarPreview = document.getElementById('avatarPreview');
    
    if (avatarInput && avatarPreview) {
        avatarInput.addEventListener('change', function(e) {
            if (e.target.files && e.target.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    avatarPreview.src = e.target.result;
                };
                reader.readAsDataURL(e.target.files[0]);
            }
        });
    }
    
    // Функционал для формы событий
    const repeatCheckbox = document.getElementById("id_repeat");
    const repeatFields = document.getElementById("repeat-fields");
    const oneTimeFields = document.getElementById("one-time-fields");

    function toggleReminderFields() {
        if (repeatCheckbox && repeatFields && oneTimeFields) {
            if (repeatCheckbox.checked) {
                repeatFields.style.display = "block";
                oneTimeFields.style.display = "none";
            } else {
                repeatFields.style.display = "none";
                oneTimeFields.style.display = "block";
            }
        }
    }

    if (repeatCheckbox) {
        repeatCheckbox.addEventListener("change", toggleReminderFields);
        toggleReminderFields();
    }
});
