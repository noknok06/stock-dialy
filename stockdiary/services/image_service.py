"""
画像処理ロジックを StockDiary / DiaryNote モデルから分離したサービス。
"""
import io
import logging
import uuid

from django.core.files.base import ContentFile
from PIL import Image

logger = logging.getLogger(__name__)


class ImageService:
    """PIL を使った画像圧縮・保存を担当するサービス。"""

    @staticmethod
    def compress_and_save(instance, image_file, max_size, quality=85):
        """image_file を圧縮して instance.image フィールドに保存する（非同期不可の初回保存用）。

        Args:
            instance: StockDiary または DiaryNote
            image_file: アップロードされた画像ファイルオブジェクト
            max_size: (width, height) のタプル
            quality: JPEG / WebP 品質（デフォルト 85）

        Returns:
            bool: 成功なら True
        """
        try:
            if instance.image:
                instance.image.delete(save=False)

            img = Image.open(image_file)
            img = ImageService._normalize_mode(img)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            output = io.BytesIO()
            try:
                img.save(output, format='WebP', quality=quality, optimize=True)
                ext = 'webp'
            except Exception:
                img.save(output, format='JPEG', quality=quality, optimize=True)
                ext = 'jpg'

            filename = f"{uuid.uuid4().hex}.{ext}"
            instance.image.save(filename, ContentFile(output.getvalue()), save=False)
            instance.save(update_fields=['image'])
            return True

        except Exception as e:
            logger.error(
                "Image processing failed for %s(id=%s): %s",
                type(instance).__name__, getattr(instance, 'id', '?'), e,
                exc_info=True,
            )
            return False

    @staticmethod
    def compress_stored(instance, max_size, quality=85):
        """既に DB に保存済みの instance.image を圧縮・上書きする（非同期タスク用）。

        Args:
            instance: StockDiary または DiaryNote（image フィールドが保存済みであること）
            max_size: (width, height) のタプル
            quality: JPEG / WebP 品質

        Returns:
            bool: 成功なら True
        """
        try:
            with instance.image.open('rb') as f:
                img = Image.open(f)
                img.load()

            img = ImageService._normalize_mode(img)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            output = io.BytesIO()
            try:
                img.save(output, format='WebP', quality=quality, optimize=True)
                ext = 'webp'
            except Exception:
                img.save(output, format='JPEG', quality=quality, optimize=True)
                ext = 'jpg'

            old_name = instance.image.name
            instance.image.delete(save=False)
            filename = f"{uuid.uuid4().hex}.{ext}"
            instance.image.save(filename, ContentFile(output.getvalue()), save=False)
            instance.save(update_fields=['image'])

            logger.debug(
                "Compressed stored image for %s(id=%s): %s → %s",
                type(instance).__name__, instance.id, old_name, instance.image.name,
            )
            return True

        except Exception as e:
            logger.error(
                "Stored image compression failed for %s(id=%s): %s",
                type(instance).__name__, getattr(instance, 'id', '?'), e,
                exc_info=True,
            )
            return False

    @staticmethod
    def _normalize_mode(img):
        """RGBA / LA / P モードを RGB に変換する。"""
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            return background
        return img
