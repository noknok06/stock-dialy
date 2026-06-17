"""日記データ移行（エクスポート/インポート）ビュー。

別アカウント/別環境へのデータ移行を目的に、StockDiary とその関連
（継続記録・取引・株式分割・タグ・タグ方向・仮説・検証）を JSON または CSV(ZIP) で出力し、
同形式のファイルから取り込む。

証券会社CSV取り込み（trade_upload）とは別機能。混同を避けるため別ページ・別動線。
シリアライズ本体は services/migration_export_service.py / migration_import_service.py。
"""

import json
import traceback

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import DataExportForm, DataImportForm
from .services.migration_export_service import ExportService
from .services.migration_import_service import ImportService, ImportError as MigrationImportError

# セッションに検証済み payload を保持するキー
SESSION_PAYLOAD_KEY = 'migration_import_payload'
SESSION_FILENAME_KEY = 'migration_import_filename'


class MigrationExportView(LoginRequiredMixin, FormView):
    """エクスポート入口（形式選択）。"""
    template_name = 'stockdiary/migration_export.html'
    form_class = DataExportForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        return context

    def form_valid(self, form):
        export_format = form.cleaned_data['export_format']
        return _download_export(self.request.user, export_format)


@login_required
def migration_export_download(request):
    """GET でのダウンロード用エンドポイント（?format=json|csv）。"""
    export_format = request.GET.get('format', 'json')
    return _download_export(request.user, export_format)


def _download_export(user, export_format):
    service = ExportService(user)
    if export_format == 'csv':
        filename, content = service.to_csv_zip()
        content_type = 'application/zip'
    else:
        filename, content = service.to_json()
        content_type = 'application/json; charset=utf-8'

    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


class MigrationImportView(LoginRequiredMixin, FormView):
    """インポート入口（ファイル選択）→ パース・検証 → プレビューへ。"""
    template_name = 'stockdiary/migration_import.html'
    form_class = DataImportForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_actions'] = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            }
        ]
        return context

    def form_valid(self, form):
        data_file = form.cleaned_data['data_file']
        service = ImportService(self.request.user)

        try:
            payload = service.parse(data_file)
            warnings = service.validate(payload)
        except MigrationImportError as e:
            messages.error(self.request, f'ファイルの読み込みに失敗しました: {e}')
            return self.form_invalid(form)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            messages.error(self.request, f'予期しないエラーが発生しました: {e}')
            return self.form_invalid(form)

        # 検証済み payload をセッションに保持（本登録で再利用）
        self.request.session[SESSION_PAYLOAD_KEY] = json.dumps(payload, ensure_ascii=False)
        self.request.session[SESSION_FILENAME_KEY] = data_file.name

        for w in warnings[:10]:
            messages.warning(self.request, w)

        return redirect('stockdiary:migration_import_process')


@login_required
def migration_import_process(request):
    """GET=プレビュー描画 / POST=本登録。"""
    payload_json = request.session.get(SESSION_PAYLOAD_KEY)
    filename = request.session.get(SESSION_FILENAME_KEY, '不明')

    if not payload_json:
        messages.error(request, 'インポートデータが見つかりません。もう一度ファイルを選択してください。')
        return redirect('stockdiary:migration_import')

    payload = json.loads(payload_json)
    service = ImportService(request.user)

    if request.method != 'POST':
        # プレビュー表示
        try:
            summary = service.summarize(payload)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            messages.error(request, f'プレビューの生成に失敗しました: {e}')
            return redirect('stockdiary:migration_import')

        context = {
            'filename': filename,
            'summary': summary,
        }
        return render(request, 'stockdiary/migration_import_preview.html', context)

    # 本登録
    try:
        result = service.import_payload(payload)
    except MigrationImportError as e:
        messages.error(request, f'インポートに失敗しました: {e}')
        return redirect('stockdiary:migration_import')
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        messages.error(request, f'インポート中にエラーが発生しました: {e}')
        return redirect('stockdiary:migration_import')

    # セッションクリア
    request.session.pop(SESSION_PAYLOAD_KEY, None)
    request.session.pop(SESSION_FILENAME_KEY, None)

    messages.success(
        request,
        f'インポートが完了しました。'
        f'日記: {result["created_diaries"]}件、'
        f'取引: {result["transactions"]}件、'
        f'継続記録: {result["notes"]}件、'
        f'株式分割: {result["stock_splits"]}件、'
        f'仮説: {result["theses"]}件、'
        f'検証: {result["verdicts"]}件、'
        f'タグ: 新規{result["tags_created"]}/再利用{result["tags_reused"]}件'
    )
    if result['skipped_diaries']:
        messages.warning(request, f'{result["skipped_diaries"]}件の日記は銘柄名が空のためスキップしました')
    for w in result['warnings'][:5]:
        messages.warning(request, w)

    return redirect('stockdiary:home')
