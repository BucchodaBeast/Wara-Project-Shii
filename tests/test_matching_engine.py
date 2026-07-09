"""
Unit tests for app.matching_engine — no DB or network required.
Run with:  python -m pytest tests/ -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.matching_engine import (
    haversine_km, proximity_score, resource_type_score, score_pair, compute_matches
)


def test_haversine_zero_distance():
    assert haversine_km(-26.30, 31.13, -26.30, 31.13) == 0


def test_haversine_known_distance():
    # Mbabane to Manzini, Eswatini — roughly 30-40km apart
    d = haversine_km(-26.3054, 31.1367, -26.4833, 31.3833)
    assert 25 < d < 45


def test_haversine_missing_coords_treated_as_far():
    d = haversine_km(None, None, -26.30, 31.13)
    assert d >= 50


def test_proximity_score_bounds():
    assert proximity_score(0) == 1.0
    assert proximity_score(50) == 0.0
    assert proximity_score(100) == 0.0
    assert 0 < proximity_score(25) < 1


def test_resource_type_exact_match():
    assert resource_type_score("water", "water") == 1.0


def test_resource_type_related_match():
    assert resource_type_score("medical", "first_aid") == 0.5


def test_resource_type_unrelated():
    assert resource_type_score("water", "shelter") == 0.1


def test_score_pair_critical_close_exact_match_scores_high():
    request_row = {"category": "water", "urgency": "critical", "latitude": -26.30, "longitude": 31.13}
    offer_row = {"resource_type": "water", "latitude": -26.30, "longitude": 31.13}
    result = score_pair(request_row, offer_row)
    assert result["score"] > 90


def test_score_pair_low_urgency_far_unrelated_scores_low():
    request_row = {"category": "water", "urgency": "low", "latitude": -26.30, "longitude": 31.13}
    offer_row = {"resource_type": "shelter", "latitude": -27.50, "longitude": 32.50}
    result = score_pair(request_row, offer_row)
    assert result["score"] < 25


def test_compute_matches_sorted_descending():
    request_row = {"id": 1, "category": "water", "urgency": "critical", "latitude": -26.30, "longitude": 31.13}
    offers = [
        {"id": 1, "resource_type": "shelter", "latitude": -27.50, "longitude": 32.50},
        {"id": 2, "resource_type": "water", "latitude": -26.30, "longitude": 31.13},
    ]
    results = compute_matches(request_row, offers)
    assert results[0]["offer_id"] == 2
    assert results[0]["score"] >= results[1]["score"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
