# common/services/margin_ratio_service.py
# 信用倍率データ取得・保存サービス
#
# ■ データソース方針
#   - yfinance: shortRatio（空売りカバー日数）を参考指標として取得
#   - 正式な信用倍率（信用買い残/信用売り残）は TSE 週次データが必要。
#     本サービスは将来の正式データ統合に向けたインフラを提供する。
#
# ■ 信用倍率とは
#   信用買い残 ÷ 信用売り残 の比率（東証が毎週金曜公表）
#   - 高い（>5）: 買い方が多い。将来の売り圧力が大きい可能性
#   - 低い（<1）: 売り方が多い。踏み上げ（ショートスクイーズ）リスク

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class MarginRatioService:
    """信用倍率データ取得・管理サービス"""

    # 更新間隔（日） — 週次データなので7日
    REFRESH_INTERVAL_DAYS = 7

    def get_or_fetch(self, stock_symbol: str, force: bool = False) -> Dict[str, Any]:
        """
        最新の信用倍率データを返す。
        直近 REFRESH_INTERVAL_DAYS 以内のデータがあればキャッシュを返し、
        なければ yfinance から取得して DB に保存する。

        Args:
            stock_symbol: 証券コード (例: "7203")
            force: 強制再取得

        Returns:
            {"success": bool, "data": MarginRatioData | None, "message": str}
        """
        from stockdiary.models import MarginRatioData
        from django.utils import timezone

        # 既存データ確認
        if not force:
            threshold = date.today() - timedelta(days=self.REFRESH_INTERVAL_DAYS)
            existing = MarginRatioData.objects.filter(
                stock_symbol=stock_symbol,
                date__gte=threshold,
            ).order_by('-date').first()
            if existing:
                return {"success": True, "data": existing, "message": "cached"}

        # yfinance から取得
        fetched = self._fetch_from_yfinance(stock_symbol)
        if not fetched["success"]:
            return fetched

        payload = fetched["payload"]

        # DB に保存（同日のデータは上書き）
        obj, _ = MarginRatioData.objects.update_or_create(
            stock_symbol=stock_symbol,
            date=payload["date"],
            defaults={
                "margin_ratio": payload.get("margin_ratio"),
                "margin_buy_balance": payload.get("margin_buy_balance"),
                "margin_sell_balance": payload.get("margin_sell_balance"),
                "short_ratio": payload.get("short_ratio"),
                "data_source": payload.get("data_source", "yfinance"),
            },
        )
        return {"success": True, "data": obj, "message": "fetched"}

    def get_history(self, stock_symbol: str, weeks: int = 52) -> List[Dict[str, Any]]:
        """
        直近 n 週分の信用倍率履歴を返す。

        Args:
            stock_symbol: 証券コード
            weeks: 取得週数（最大52週）

        Returns:
            [{"date": "YYYY-MM-DD", "margin_ratio": ..., "short_ratio": ...}, ...]
        """
        from stockdiary.models import MarginRatioData

        records = MarginRatioData.objects.filter(
            stock_symbol=stock_symbol
        ).order_by('-date')[:weeks]

        return [
            {
                "date": r.date.isoformat(),
                "margin_ratio": float(r.margin_ratio) if r.margin_ratio is not None else None,
                "margin_buy_balance": r.margin_buy_balance,
                "margin_sell_balance": r.margin_sell_balance,
                "short_ratio": float(r.short_ratio) if r.short_ratio is not None else None,
                "data_source": r.data_source,
            }
            for r in reversed(list(records))  # 古い順に並べ直す
        ]

    # ------------------------------------------------------------------
    # 内部: yfinance から取得
    # ------------------------------------------------------------------

    def _fetch_from_yfinance(self, stock_symbol: str) -> Dict[str, Any]:
        """
        yfinance から信用倍率関連データを取得する。

        yfinance で取得できる主な指標:
          shortRatio          : 空売りカバー日数（Days to Cover）
          shortPercentOfFloat : 浮動株に占める空売り比率
          sharesShort         : 空売り残高（株数）
          sharesShortPriorMonth: 前月空売り残高

        注意: これらは米国 SEC ベースのデータであり、
        日本の信用倍率（TSE 週次）とは異なる。
        日本独自の信用買い残/売り残が取得できた場合は margin_ratio に格納する。
        """
        try:
            import yfinance as yf

            ticker_symbol = f"{stock_symbol}.T"
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info or {}

            short_ratio = self._to_decimal(info.get("shortRatio"))
            shares_short = info.get("sharesShort")
            shares_short_prior = info.get("sharesShortPriorMonth")

            # 信用倍率の直接取得（yfinance では通常 None）
            # 将来的に専用データソースを接続した場合はここで計算する
            margin_ratio = None
            margin_buy_balance = None
            margin_sell_balance = None

            # shortRatio が取得できた場合は参考値として short_ratio に格納
            if short_ratio is None and short_ratio != 0:
                logger.info(
                    f"[MarginRatioService] {stock_symbol}: "
                    f"shortRatio={short_ratio}, sharesShort={shares_short}"
                )

            payload = {
                "date": date.today(),
                "margin_ratio": margin_ratio,
                "margin_buy_balance": margin_buy_balance,
                "margin_sell_balance": margin_sell_balance,
                "short_ratio": short_ratio,
                "data_source": "yfinance",
            }

            return {"success": True, "payload": payload}

        except ImportError:
            return {"success": False, "data": None, "message": "yfinance がインストールされていません"}
        except Exception as e:
            logger.warning(f"[MarginRatioService] yfinance 取得エラー ({stock_symbol}): {e}")
            return {"success": False, "data": None, "message": str(e)}

    @staticmethod
    def _to_decimal(value) -> Optional[Decimal]:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None
