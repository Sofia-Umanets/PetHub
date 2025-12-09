document.addEventListener('DOMContentLoaded', function() {
    const avatarInput = document.getElementById('id_avatar');
    const avatarPreview = document.getElementById('avatarPreview');
    
    avatarInput.addEventListener('change', function(e) {
        if (e.target.files && e.target.files[0]) {
            const reader = new FileReader();
            reader.onload = function(e) {
                avatarPreview.src = e.target.result;
            };
            reader.readAsDataURL(e.target.files[0]);
        }
    });
});