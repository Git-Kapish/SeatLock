from ticketrush_common.pagination import PaginatedResponse, PaginationParams


def test_pagination_params_offset_limit():
    p1 = PaginationParams(page=1, page_size=20)
    assert p1.offset == 0
    assert p1.limit == 20

    p2 = PaginationParams(page=3, page_size=15)
    assert p2.offset == 30
    assert p2.limit == 15


def test_paginated_response_calculations():
    items = ["item1", "item2", "item3"]
    params = PaginationParams(page=1, page_size=2)
    response = PaginatedResponse.create(items=items, total=5, params=params)

    assert response.total == 5
    assert response.page == 1
    assert response.page_size == 2
    assert response.total_pages == 3
    assert response.items == items
