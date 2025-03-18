# portfolio/models.py の修正版
from django.db import models
from django.conf import settings
from decimal import Decimal

class PortfolioSnapshot(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100)  # 例: "2023年第3四半期"
    description = models.TextField(blank=True)
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.name} ({self.created_at.strftime('%Y-%m-%d')})"

class HoldingRecord(models.Model):
    snapshot = models.ForeignKey(PortfolioSnapshot, on_delete=models.CASCADE, related_name="holdings")
    stock_symbol = models.CharField(max_length=20)
    stock_name = models.CharField(max_length=100)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    sector = models.CharField(max_length=50, blank=True)  # StockDiary から取得
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    
    def __str__(self):
        return f"{self.stock_name} ({self.snapshot.name})"

class SectorAllocation(models.Model):
    snapshot = models.ForeignKey(PortfolioSnapshot, on_delete=models.CASCADE, related_name="sector_allocations")
    sector_name = models.CharField(max_length=50)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    
    def __str__(self):
        return f"{self.sector_name}: {self.percentage}% ({self.snapshot.name})"