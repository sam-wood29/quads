import pytest

from quads.engine.logger import cents_to_float_for_db, format_money_for_logging
from quads.engine.money import fmt_money, from_cents, to_cents


class TestLoggingMoneyFormat:
    """Test money formatting for logging."""
    
    def test_format_money_for_logging(self):
        """Test that logger renders correct format."""
        # Basic cases
        assert format_money_for_logging(125) == "$1.25"
        assert format_money_for_logging(100) == "$1.00"
        assert format_money_for_logging(1) == "$0.01"
        assert format_money_for_logging(0) == "$0.00"
        assert format_money_for_logging(1234) == "$12.34"
        
        # Edge cases
        assert format_money_for_logging(99) == "$0.99"
        assert format_money_for_logging(1000) == "$10.00"
    
    def test_cents_to_float_for_db(self):
        """Test conversion from cents to float for database."""
        # Basic cases
        assert cents_to_float_for_db(125) == 1.25
        assert cents_to_float_for_db(100) == 1.0
        assert cents_to_float_for_db(1) == 0.01
        assert cents_to_float_for_db(0) == 0.0
        assert cents_to_float_for_db(1234) == 12.34
        
        # Edge cases
        assert cents_to_float_for_db(99) == 0.99
        assert cents_to_float_for_db(1000) == 10.0
    
    def test_no_rounding_drift_on_repeated_conversions(self):
        """Test that repeated conversions don't cause rounding drift."""
        # Test various amounts
        test_amounts = [0.01, 0.25, 0.50, 1.00, 12.34, 99.99, 100.00]
        
        for amount in test_amounts:
            # Convert to cents
            cents = to_cents(amount)
            
            # Convert back to float
            float_result = from_cents(cents)
            
            # Should be exactly equal
            assert float_result == amount, f"Drift detected: {amount} -> {cents} -> {float_result}"
            
            # Test multiple round trips
            for _ in range(10):
                cents = to_cents(float_result)
                float_result = from_cents(cents)
                assert float_result == amount, f"Drift after multiple conversions: {amount} -> {float_result}"
    
    def test_logging_format_consistency(self):
        """Test that logging format is consistent with fmt_money."""
        test_cases = [0, 1, 25, 100, 125, 1000, 1234, 9999]
        
        for cents in test_cases:
            # Both should produce the same result
            assert format_money_for_logging(cents) == fmt_money(cents)
    
    def test_db_conversion_consistency(self):
        """Test that DB conversion is consistent with from_cents."""
        test_cases = [0, 1, 25, 100, 125, 1000, 1234, 9999]
        
        for cents in test_cases:
            # Both should produce the same result
            assert cents_to_float_for_db(cents) == from_cents(cents)
    
    def test_edge_cases(self):
        """Test edge cases for money formatting."""
        # Zero
        assert format_money_for_logging(0) == "$0.00"
        assert cents_to_float_for_db(0) == 0.0
        
        # Single cent
        assert format_money_for_logging(1) == "$0.01"
        assert cents_to_float_for_db(1) == 0.01
        
        # Large amounts
        large_cents = 1000000  # $10,000.00
        assert format_money_for_logging(large_cents) == "$10000.00"
        assert cents_to_float_for_db(large_cents) == 10000.0
        
        # Odd amounts
        assert format_money_for_logging(123) == "$1.23"
        assert cents_to_float_for_db(123) == 1.23
    
    def test_type_validation(self):
        """Test that functions validate input types."""
        # format_money_for_logging should accept Cents
        assert format_money_for_logging(100) == "$1.00"
        
        # cents_to_float_for_db should accept Cents
        assert cents_to_float_for_db(100) == 1.0
        
        # Both should reject non-integer cents
        with pytest.raises(ValueError):
            format_money_for_logging(100.5)
        
        with pytest.raises(ValueError):
            cents_to_float_for_db(100.5) 