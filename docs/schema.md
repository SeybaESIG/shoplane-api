# Shoplane Base Schema (Step 1)

```mermaid
erDiagram
    USER ||--o{ CART : owns
    USER ||--o{ ORDER : places
    USER ||--o{ PRODUCT : updates
    USER ||--o{ CATEGORY : updates
    USER ||--o{ PAYMENT : updates
    CATEGORY ||--o{ PRODUCT : contains
    CART ||--o{ CART_ITEM : has
    PRODUCT ||--o{ CART_ITEM : references
    ORDER ||--o{ ORDER_ITEM : has
    PRODUCT ||--o{ ORDER_ITEM : references
    ORDER ||--|| PAYMENT : has
    PAYMENT ||--o{ PAYMENT_LOG : records

    USER {
      bigint user_id PK
      string role
      string first_name
      string last_name
      string email UNIQUE
      string password
      string address
      bool is_active
      datetime created_at
      datetime updated_at
      bigint updated_by FK
    }

    CATEGORY {
      bigint category_id PK
      string name UNIQUE
      string slug UNIQUE
      string description
      bool is_active
      datetime created_at
      datetime updated_at
      bigint updated_by FK
    }

    PRODUCT {
      bigint product_id PK
      bigint category_id FK
      string product_name
      string product_slug UNIQUE
      string description
      decimal price
      int stock
      bool is_active
      bool is_deleted
      datetime created_at
      datetime updated_at
      bigint updated_by FK
    }

    CART {
      bigint cart_id PK
      bigint user_id FK
      string status
      decimal total_price
      datetime created_at
      datetime updated_at
    }

    CART_ITEM {
      bigint cartitem_id PK
      bigint cart_id FK
      bigint product_id FK
      int quantity
      decimal unit_price
      decimal subtotal
    }

    ORDER {
      bigint order_id PK
      bigint user_id FK
      string order_number UNIQUE
      decimal total_price
      string status
      string shipping_address
      string billing_address
      datetime created_at
    }

    ORDER_ITEM {
      bigint orderitem_id PK
      bigint order_id FK
      bigint product_id FK
      int quantity
      decimal unit_price
      decimal subtotal
    }

    PAYMENT {
      bigint payment_id PK
      bigint order_id FK UNIQUE
      decimal amount
      string provider
      string transaction_ref UNIQUE
      string status
      datetime paid_at
      datetime refunded_at
      datetime created_at
      datetime updated_at
    }

    PAYMENT_LOG {
      bigint paymentlog_id PK
      bigint payment_id FK
      string event_type
      string message
      json data
      datetime created_at
    }
```

## Enum definitions

- `User.role`: `ADMIN`, `USER`
- `Cart.status`: `OPEN`, `SUBMITTED`, `CONVERTED`
- `Order.status`: `PENDING`, `CONFIRMED`, `CANCELLED`
- `Payment.status`: `PENDING`, `PAID`, `FAILED`, `REFUNDED`
