"""
Standard pagination for list endpoints.

Usage in a view:
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    data = SomeSerializer(page, many=True).data
    return success_response(
        message="...",
        data=data,
        meta=paginator.get_meta(),
    )
"""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Page-number pagination with a configurable page size.
    Default: 20 items per page. Maximum: 100.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_meta(self):
        """Return a dict suitable for the 'meta' key in the response envelope."""
        return {
            "count": self.page.paginator.count,
            "page": self.page.number,
            "page_size": self.get_page_size(self.request),
            "total_pages": self.page.paginator.num_pages,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
        }
