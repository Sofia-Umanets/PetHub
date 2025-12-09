from django.shortcuts import render, get_object_or_404, redirect
from django.views import generic
from django.urls import reverse_lazy, reverse
from .forms import CustomUserCreationForm, UserEditForm
from pets.models import Pet
from django.contrib.auth.decorators import login_required
from .models import PetInvite
from django.http import JsonResponse
from .models import UserNotification
from django.views.decorators.http import require_POST
from django.contrib import messages

class SignupPageView(generic.CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'registration/signup.html'

@login_required
def profile(request):
    pets = Pet.objects.filter(owners=request.user)
    notifications = request.user.usernotification_set.filter(is_read=False)

    return render(request, 'accounts/profile.html', {
        'pets': pets,
        'notifications': notifications,
    })

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = UserEditForm(
            request.POST, 
            request.FILES, 
            instance=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки.')
    else:
        form = UserEditForm(instance=request.user)

    return render(request, 'accounts/edit_profile.html', {
        'form': form,
        'user': request.user
    })

@login_required
def invite_owner(request, pet_id):
    pet = get_object_or_404(Pet, id=pet_id)

    if request.user not in pet.owners.all():
        return redirect('pets:list')

    invite = PetInvite.objects.create(pet=pet, created_by=request.user)
    invite_link = request.build_absolute_uri(
        reverse('accept_invite', args=[str(invite.token)])
    )

    return render(request, 'accounts/invite_link.html', {
        'invite_link': invite_link,
        'pet': pet
    })

def accept_invite(request, token):
    try:
        invite = PetInvite.objects.get(token=token)
    except PetInvite.DoesNotExist:
        return render(request, 'error/invite_invalid.html')
    
    if invite.is_used:
        return render(request, 'error/invite_already_used.html', {'invite': invite})

    if request.user.is_authenticated:
        invite.pet.owners.add(request.user)
        invite.is_used = True
        invite.save()
        return redirect('pets:detail', pet_id=invite.pet.id)
    
    login_url = reverse('account_login')  
    return redirect(f"{login_url}?next={request.path}")

@login_required
def mark_notification_read(request, notification_id):
    notif = get_object_or_404(UserNotification, pk=notification_id, user=request.user)
    if request.method == "POST":
        notif.is_read = True
        notif.save()
        return redirect(request.META.get('HTTP_REFERER', '/'))
    return redirect('/')