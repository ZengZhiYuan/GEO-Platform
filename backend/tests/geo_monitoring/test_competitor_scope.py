from app.geo_monitoring.services.competitor_scope import resolve_competitor_brand_ids


class _Brand:
    def __init__(self, brand_id: int, brand_type: str):
        self.id = brand_id
        self.brand_type = brand_type


class _Mention:
    def __init__(self, brand_id: int, is_mentioned: bool):
        self.brand_id = brand_id
        self.is_mentioned = is_mentioned


class _Answer:
    def __init__(self, mentions):
        self.brand_results = mentions


def test_configured_competitors_always_included():
    brands = [
        _Brand(1, "target"),
        _Brand(2, "competitor"),
        _Brand(3, "competitor"),
        _Brand(4, "candidate"),
    ]
    answers = [_Answer([_Mention(4, True)])]
    result = resolve_competitor_brand_ids(
        brands=brands,
        target_brand_id=1,
        answers=answers,
    )
    assert result == (2, 3)


def test_discovered_competitors_when_none_configured():
    brands = [
        _Brand(1, "target"),
        _Brand(4, "candidate"),
        _Brand(5, "candidate"),
    ]
    answers = [
        _Answer([_Mention(4, True), _Mention(5, False)]),
        _Answer([_Mention(5, True)]),
    ]
    result = resolve_competitor_brand_ids(
        brands=brands,
        target_brand_id=1,
        answers=answers,
    )
    assert result == (4, 5)
