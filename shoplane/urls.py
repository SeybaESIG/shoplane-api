from django.urls import path

from .auth_views import JWTLoginView, JWTLogoutView, JWTRefreshView, JWTVerifyView, RegisterView
from .cart_views import CartItemView, CartView
from .category_views import CategoryViewSet
from .export_views import CustomerExportView, OrderExportView
from .order_views import OrderDetailView, OrderListCreateView
from .payment_views import PaymentLogView, PaymentView
from .product_views import ProductViewSet
from .stats_views import (
    AverageCartView,
    CustomerRecurrenceView,
    OrdersPerCustomerView,
    SalesStatsView,
    TopProductsView,
)
from .user_views import MeView
from .views import health

category_list = CategoryViewSet.as_view({"get": "list", "post": "create"})
category_detail = CategoryViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

product_list = ProductViewSet.as_view({"get": "list", "post": "create"})
product_detail = ProductViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", JWTLoginView.as_view(), name="jwt-login"),
    path("auth/refresh/", JWTRefreshView.as_view(), name="jwt-refresh"),
    path("auth/verify/", JWTVerifyView.as_view(), name="jwt-verify"),
    path("auth/logout/", JWTLogoutView.as_view(), name="jwt-logout"),
    path("categories/", category_list, name="category-list"),
    path("categories/<slug:slug>/", category_detail, name="category-detail"),
    path("products/", product_list, name="product-list"),
    path("products/<slug:slug>/", product_detail, name="product-detail"),
    path("users/me/", MeView.as_view(), name="user-me"),
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/items/", CartItemView.as_view(), name="cart-item-add"),
    path("cart/items/<slug:product_slug>/", CartItemView.as_view(), name="cart-item-detail"),
    path("orders/", OrderListCreateView.as_view(), name="order-list"),
    path("orders/<str:order_number>/", OrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:order_number>/payment/", PaymentView.as_view(), name="payment"),
    path("orders/<str:order_number>/payment/logs/", PaymentLogView.as_view(), name="payment-logs"),
    path("exports/orders/", OrderExportView.as_view(), name="export-orders"),
    path("exports/customers/", CustomerExportView.as_view(), name="export-customers"),
    path("stats/top-products/", TopProductsView.as_view(), name="stats-top-products"),
    path("stats/sales/", SalesStatsView.as_view(), name="stats-sales"),
    path("stats/average-cart/", AverageCartView.as_view(), name="stats-average-cart"),
    path(
        "stats/orders-per-customer/",
        OrdersPerCustomerView.as_view(),
        name="stats-orders-per-customer",
    ),
    path(
        "stats/customer-recurrence/",
        CustomerRecurrenceView.as_view(),
        name="stats-customer-recurrence",
    ),
]
