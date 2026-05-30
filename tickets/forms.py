from django import forms
from django.contrib.auth import get_user_model
from .models import Ticket, TicketComment
from django import forms
from django.forms.widgets import ClearableFileInput


# ── Widget personnalisé pour upload multiple ──────────────────────────────
class MultipleFileInput(ClearableFileInput):
    """Compatible Django 4.2+ — autorise plusieurs fichiers."""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Champ fichier acceptant plusieurs fichiers simultanément."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(
            attrs={'class': 'form-control'}
        ))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # data peut être une liste de fichiers ou un seul
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data]
        return single(data, initial)



User = get_user_model()


class TicketCreateForm(forms.ModelForm):
    
    attachments = MultipleFileField(
        required=False,
        label="Pièces jointes",
    )

    class Meta:
        model = Ticket
        fields = ['type', 'title', 'description', 'priority', 'category',  'tags']
        widgets = {
            'type':        forms.Select(attrs={'class': 'form-select'}),
            'title':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titre du ticket'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'priority':    forms.Select(attrs={'class': 'form-select'}),
            'category':    forms.Select(attrs={'class': 'form-select'}),
            'source':      forms.Select(attrs={'class': 'form-select'}),
            'tags':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'tag1, tag2, tag3'}),
        }


class TicketUpdateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'priority', 'category', 'tags']
        widgets = {
            'title':       forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'priority':    forms.Select(attrs={'class': 'form-select'}),
            'category':    forms.Select(attrs={'class': 'form-select'}),
            'tags':        forms.TextInput(attrs={'class': 'form-control'}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ['content', 'visibility']
        widgets = {
            'content':    forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Votre commentaire…'}),
            'visibility': forms.Select(attrs={'class': 'form-select'}),
        }


class AssignForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = User.objects.filter(
            role__in=['AGENT', 'L2_AGENT'], is_active=True
        ).order_by('last_name', 'first_name')
        self.fields['assignee'].widget.attrs['class'] = 'form-select'
        self.fields['assignee'].label = 'Assigner à'
        self.fields['assignee'].required = False

    class Meta:
        model = Ticket
        fields = ['assignee']
