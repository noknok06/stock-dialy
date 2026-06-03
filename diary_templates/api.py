from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import DiaryTemplate


@login_required
@require_GET
def list_templates(request):
    templates = DiaryTemplate.objects.filter(user=request.user).values('id', 'title')
    return JsonResponse({
        'success': True,
        'templates': list(templates),
    })


@login_required
@require_GET
def get_template(request, pk):
    template = get_object_or_404(DiaryTemplate, pk=pk, user=request.user)
    return JsonResponse({
        'success': True,
        'template': {
            'id': template.id,
            'title': template.title,
            'body': template.body,
        },
    })
