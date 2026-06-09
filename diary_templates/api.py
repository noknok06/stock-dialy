from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .defaults import BASIC_TEMPLATE_TITLE
from .models import DiaryTemplate


@login_required
@require_GET
def list_templates(request):
    # 「基本テンプレート」を先頭に、それ以外はタイトル順で返す。
    templates = (
        DiaryTemplate.objects.filter(user=request.user)
        .annotate(
            _priority=Case(
                When(title=BASIC_TEMPLATE_TITLE, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by('_priority', 'title')
        .values('id', 'title')
    )
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
