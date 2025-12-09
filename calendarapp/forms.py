from django import forms
from .models import ReminderSettings

class ReminderSettingsForm(forms.ModelForm):
    class Meta:
        model = ReminderSettings
        fields = ['remind_at', 'repeat', 'repeat_days', 'repeat_every', 'remind_date']
        widgets = {
            'remind_at': forms.TimeInput(attrs={'type': 'time'}),
            'remind_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        repeat = cleaned.get('repeat')
        date = cleaned.get('remind_date')
        days = cleaned.get('repeat_days')

        if not repeat and not date:
            raise forms.ValidationError("Если напоминание не повторяется, нужно указать дату.")
        if repeat and not days:
            raise forms.ValidationError("Если напоминание повторяется, нужно выбрать дни недели.")
        return cleaned
