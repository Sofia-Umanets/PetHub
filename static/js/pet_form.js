
function toggleCustomPetType() {
    const petTypeSelect = document.getElementById('pet_type');
    const customGroup = document.getElementById('custom_pet_type_group');
    const customInput = document.getElementById('custom_pet_type');
    
    if (petTypeSelect.value === 'other') {
        customGroup.style.display = 'block';
        customInput.required = true;
    } else {
        customGroup.style.display = 'none';
        customInput.required = false;
        customInput.value = '';
    }
}

document.addEventListener('DOMContentLoaded', toggleCustomPetType);