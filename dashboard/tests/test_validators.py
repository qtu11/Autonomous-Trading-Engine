"""
Unit Tests for Validators
"""
import pytest
from validators import (
    validate_symbol,
    validate_timeframe,
    validate_price,
    sanitize_input,
    AnalyzeRequest,
    OrderRequest,
    RiskProfileRequest,
    SymbolEnum,
    TimeframeEnum,
    DirectionEnum
)
from pydantic import ValidationError


class TestSymbolValidation:
    """Test symbol validation"""
    
    def test_valid_symbols(self):
        """Test valid trading symbols"""
        assert validate_symbol("BTCUSDT") == True
        assert validate_symbol("ETHUSDT") == True
        assert validate_symbol("XAUUSD") == True
        assert validate_symbol("BNBUSDT") == True
    
    def test_invalid_symbols(self):
        """Test invalid symbols"""
        assert validate_symbol("INVALID") == False
        assert validate_symbol("123") == False
        assert validate_symbol("") == False
        assert validate_symbol("BTC") == False


class TestTimeframeValidation:
    """Test timeframe validation"""
    
    def test_valid_timeframes(self):
        """Test valid timeframes"""
        assert validate_timeframe("M1") == True
        assert validate_timeframe("M15") == True
        assert validate_timeframe("H1") == True
        assert validate_timeframe("H4") == True
        assert validate_timeframe("D1") == True
    
    def test_invalid_timeframes(self):
        """Test invalid timeframes"""
        assert validate_timeframe("M2") == False
        assert validate_timeframe("H2") == False
        assert validate_timeframe("INVALID") == False


class TestPriceValidation:
    """Test price validation"""
    
    def test_valid_prices(self):
        """Test valid prices"""
        assert validate_price(100.0) == True
        assert validate_price(0.0001) == True
        assert validate_price(50000.0) == True
    
    def test_invalid_prices(self):
        """Test invalid prices"""
        assert validate_price(0) == False
        assert validate_price(-100) == False
        assert validate_price(0.00001) == False


class TestSanitizeInput:
    """Test input sanitization"""
    
    def test_sanitize_normal_input(self):
        """Test normal input"""
        assert sanitize_input("hello") == "hello"
        assert sanitize_input("test123") == "test123"
    
    def test_sanitize_injection(self):
        """Test injection prevention"""
        assert sanitize_input("<script>alert(1)</script>") == "scriptalert(1)/script"
        assert sanitize_input("'; DROP TABLE--") == "DROPTABLE--"
    
    def test_sanitize_length(self):
        """Test max length"""
        long_string = "a" * 200
        result = sanitize_input(long_string)
        assert len(result) == 100


class TestPydanticModels:
    """Test Pydantic request models"""
    
    def test_analyze_request_valid(self):
        """Test valid analyze request"""
        req = AnalyzeRequest(symbol="BTCUSDT", timeframe="M15", count=500)
        assert req.symbol == "BTCUSDT"
        assert req.count == 500
    
    def test_analyze_request_invalid_count(self):
        """Test invalid count"""
        with pytest.raises(ValidationError):
            AnalyzeRequest(symbol="BTCUSDT", count=10000)
    
    def test_order_request_valid(self):
        """Test valid order request"""
        req = OrderRequest(
            symbol="BTCUSDT",
            direction="long",
            quantity=0.1,
            entry_price=50000,
            stop_loss=49000,
            take_profit=52000
        )
        assert req.direction == "long"
    
    def test_order_request_invalid_quantity(self):
        """Test invalid quantity"""
        with pytest.raises(ValidationError):
            OrderRequest(
                symbol="BTCUSDT",
                direction="long",
                quantity=200  # Exceeds max of 100
            )
    
    def test_risk_profile_valid(self):
        """Test valid risk profile"""
        req = RiskProfileRequest(
            max_risk_per_trade=1.0,
            max_daily_loss=5.0,
            max_open_trades=3
        )
        assert req.position_size_method == "fixed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
