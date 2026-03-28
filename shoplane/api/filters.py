"""
Query parameter filtering and ordering helpers.

Each function takes a queryset and a request, applies the relevant
query parameters, and returns the filtered/ordered queryset.
"""

from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# Allowed ordering fields per resource. Prefix with '-' for descending.
# ---------------------------------------------------------------------------

PRODUCT_ORDERING_FIELDS = {"price", "name", "created_at"}
CATEGORY_ORDERING_FIELDS = {"name", "created_at"}
ORDER_ORDERING_FIELDS = {"created_at", "total_price", "status"}


def _parse_ordering(value, allowed_fields):
    """
    Validate and return an ordering string safe to pass to queryset.order_by().
    Returns None if the value is not in the allowed set.
    """
    field = value.lstrip("-")
    if field in allowed_fields:
        return value
    return None


def filter_products(queryset, request):
    """
    Apply filtering, search, and ordering to a product queryset.

    Supported query parameters:
      ?category=<slug>          -- filter by category slug
      ?min_price=<decimal>      -- minimum price (inclusive)
      ?max_price=<decimal>      -- maximum price (inclusive)
      ?in_stock=true            -- exclude products with stock=0
      ?search=<text>            -- case-insensitive match on product name
      ?ordering=<field>         -- sort field; prefix with '-' for descending
                                   allowed: price, name, created_at
    """
    params = request.query_params

    category = params.get("category")
    if category:
        queryset = queryset.filter(category__slug=category)

    min_price = params.get("min_price")
    if min_price:
        try:
            queryset = queryset.filter(price__gte=Decimal(min_price))
        except InvalidOperation:
            pass

    max_price = params.get("max_price")
    if max_price:
        try:
            queryset = queryset.filter(price__lte=Decimal(max_price))
        except InvalidOperation:
            pass

    in_stock = params.get("in_stock")
    if in_stock == "true":
        queryset = queryset.filter(stock__gt=0)

    search = params.get("search")
    if search:
        queryset = queryset.filter(name__icontains=search)

    ordering = params.get("ordering")
    if ordering:
        safe_ordering = _parse_ordering(ordering, PRODUCT_ORDERING_FIELDS)
        if safe_ordering:
            queryset = queryset.order_by(safe_ordering)

    return queryset


def filter_categories(queryset, request):
    """
    Apply ordering to a category queryset.

    Supported query parameters:
      ?ordering=<field>   -- allowed: name, created_at
    """
    ordering = request.query_params.get("ordering")
    if ordering:
        safe_ordering = _parse_ordering(ordering, CATEGORY_ORDERING_FIELDS)
        if safe_ordering:
            queryset = queryset.order_by(safe_ordering)

    return queryset


def filter_orders(queryset, request):
    """
    Apply filtering and ordering to an order queryset.

    Supported query parameters:
      ?status=<value>     -- filter by exact status (PENDING, CONFIRMED, CANCELLED)
      ?ordering=<field>   -- allowed: created_at, total_price, status
    """
    params = request.query_params

    order_status = params.get("status")
    if order_status:
        queryset = queryset.filter(status=order_status.upper())

    ordering = params.get("ordering")
    if ordering:
        safe_ordering = _parse_ordering(ordering, ORDER_ORDERING_FIELDS)
        if safe_ordering:
            queryset = queryset.order_by(safe_ordering)

    return queryset
