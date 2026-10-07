"""Business logic for the tau2-bench retail domain.

Ported from sierra-research/tau2-bench (src/tau2/domains/retail/data_model.py
and tools.py, MIT license, see retail/source/TAU2_BENCH_LICENSE.txt). The data
model and tool bodies are tau2's; only the class wrapper is gone. Each action
takes a ``RetailDB``, mutates it the same way the tau2 tool did, and returns the
string tau2's environment would send back to the agent: the result serialized
as JSON, or ``"Error: <message>"`` when the tool raised. Keeping this module free
of ADK imports lets the offline tests replay tau2's gold actions without an
Orchestrate server.
"""

import functools
import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).parent / "data"


# --- Data model (tau2/domains/retail/data_model.py) -------------------------


class Variant(BaseModel):
    """Represents a specific variant of a product with its options, availability and price"""

    item_id: str = Field(description="Unique identifier for the variant")
    options: Dict[str, str] = Field(
        description="Dictionary of option names to values (e.g. {'color': 'blue', 'size': 'large'})"
    )
    available: bool = Field(description="Whether this variant is currently in stock")
    price: float = Field(description="Price of this variant")


class Product(BaseModel):
    """Represents a product with its variants"""

    name: str = Field(description="Name of the product")
    product_id: str = Field(description="Unique identifier for the product")
    variants: Dict[str, Variant] = Field(description="Dictionary of variants indexed by variant ID")


class UserName(BaseModel):
    """Represents a user's full name"""

    first_name: str = Field(description="User's first name")
    last_name: str = Field(description="User's last name")


class UserAddress(BaseModel):
    """Represents a physical address"""

    address1: str = Field(description="Primary address line")
    address2: str = Field(description="Secondary address line")
    city: str = Field(description="City name")
    country: str = Field(description="Country name")
    state: str = Field(description="State or province name")
    zip: str = Field(description="Postal code")


class PaymentMethodBase(BaseModel):
    source: str = Field(description="Type of payment method")
    id: str = Field(description="Unique identifier for the payment method")


class CreditCard(PaymentMethodBase):
    source: Literal["credit_card"] = Field(description="Indicates this is a credit card payment method")
    brand: str = Field(description="Credit card brand (e.g., visa, mastercard)")
    last_four: str = Field(description="Last four digits of the credit card")


class Paypal(PaymentMethodBase):
    source: Literal["paypal"] = Field(description="Indicates this is a paypal payment method")


class GiftCard(PaymentMethodBase):
    source: Literal["gift_card"] = Field(description="Indicates this is a gift card payment method")
    balance: float = Field(description="Gift card value amount")
    id: str = Field(description="Unique identifier for the gift card")


PaymentMethod = Union[CreditCard, GiftCard, Paypal]


class User(BaseModel):
    """Represents a user with their personal information, payment methods and order history"""

    user_id: str = Field(description="Unique identifier for the user")
    name: UserName = Field(description="User's full name")
    address: UserAddress = Field(description="User's primary address")
    email: str = Field(description="User's email address")
    payment_methods: Dict[str, PaymentMethod] = Field(
        description="Dictionary of payment methods indexed by payment method ID"
    )
    orders: List[str] = Field(description="List of order IDs associated with this user")


class OrderFullfilment(BaseModel):
    """Represents the fulfillment details for items in an order"""

    tracking_id: list[str] = Field(description="List of tracking IDs for shipments")
    item_ids: list[str] = Field(description="List of item IDs included in this fulfillment")


class OrderItem(BaseModel):
    """Represents an item in an order"""

    name: str = Field(description="Name of the product")
    product_id: str = Field(description="ID of the product")
    item_id: str = Field(description="ID of the specific variant")
    price: float = Field(description="Price of the item at time of purchase")
    options: Dict[str, str] = Field(description="Options selected for this item")


OrderPaymentType = Literal["payment", "refund"]


class OrderPayment(BaseModel):
    """Represents a payment or refund transaction for an order"""

    transaction_type: OrderPaymentType = Field(description="Type of transaction (payment or refund)")
    amount: float = Field(description="Amount of the transaction")
    payment_method_id: str = Field(description="ID of the payment method used")


OrderStatus = Literal[
    "processed",
    "pending",
    "pending (item modified)",
    "delivered",
    "cancelled",
    "exchange requested",
    "return requested",
]

CancelReason = Literal["no longer needed", "ordered by mistake"]


class Order(BaseModel):
    """Represents an order with its items, status, fulfillment and payment details"""

    order_id: str = Field(description="Unique identifier for the order")
    user_id: str = Field(description="Unique identifier for the user")
    address: UserAddress = Field(description="Address of the user")
    items: List[OrderItem] = Field(description="Items in the order")
    status: OrderStatus = Field(description="Status of the order")
    fulfillments: List[OrderFullfilment] = Field(description="Fulfillments of the order")
    payment_history: List[OrderPayment] = Field(description="Payments of the order")
    cancel_reason: Optional[CancelReason] = Field(
        description="Reason for cancelling the order. Should be 'no longer needed' or 'ordered by mistake'",
        default=None,
    )
    exchange_items: Optional[List[str]] = Field(description="Items to be exchanged", default=None)
    exchange_new_items: Optional[List[str]] = Field(description="Items exchanged for", default=None)
    exchange_payment_method_id: Optional[str] = Field(
        description="Payment method ID for the exchange", default=None
    )
    exchange_price_difference: Optional[float] = Field(
        description="Price difference for the exchange", default=None
    )
    return_items: Optional[List[str]] = Field(description="Items to be returned", default=None)
    return_payment_method_id: Optional[str] = Field(
        description="Payment method ID for the return", default=None
    )


class RetailDB(BaseModel):
    """Database containing all retail-related data including products, users and orders"""

    products: Dict[str, Product] = Field(description="Dictionary of all products indexed by product ID")
    users: Dict[str, User] = Field(description="Dictionary of all users indexed by user ID")
    orders: Dict[str, Order] = Field(description="Dictionary of all orders indexed by order ID")


def load_data() -> RetailDB:
    return RetailDB.model_validate_json((DATA_DIR / "db.json").read_text())


# --- Result serialization (tau2/environment/environment.py) -----------------


def to_json_str(resp: Any) -> str:
    """Serialize a tool result the way tau2's Environment.to_json_str does."""

    def _process(resp: Any) -> Any:
        if isinstance(resp, BaseModel):
            return resp.model_dump()
        if isinstance(resp, str) or resp is None:
            return resp
        if isinstance(resp, (int, float, bool)):
            return str(resp)
        if isinstance(resp, (list, tuple)):
            return [_process(item) for item in resp]
        if isinstance(resp, dict):
            return {k: _process(v) for k, v in resp.items()}
        raise ValueError(f"Unsupported type: {type(resp)}")

    if not isinstance(resp, str):
        return json.dumps(_process(resp), default=str)
    return resp


def _action(fn):
    """Return tau2's tool message: the serialized result, or "Error: ..." if the tool raised."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> str:
        try:
            resp = fn(*args, **kwargs)
        except Exception as e:
            return f"Error: {e}"
        return to_json_str(resp)

    return wrapper


# --- Helpers (RetailTools private methods) ----------------------------------


def _get_order(db: RetailDB, order_id: str) -> Order:
    if order_id not in db.orders:
        raise ValueError("Order not found")
    return db.orders[order_id]


def _get_user(db: RetailDB, user_id: str) -> User:
    if user_id not in db.users:
        raise ValueError("User not found")
    return db.users[user_id]


def _get_product(db: RetailDB, product_id: str) -> Product:
    if product_id not in db.products:
        raise ValueError("Product not found")
    return db.products[product_id]


def _get_item(db: RetailDB, item_id: str) -> Variant:
    for _, product in db.products.items():
        if item_id in product.variants:
            return product.variants[item_id]
    raise ValueError("Item not found")


def _get_variant(db: RetailDB, product_id: str, variant_id: str) -> Variant:
    product = _get_product(db, product_id)
    if variant_id not in product.variants:
        raise ValueError("Variant not found")
    return product.variants[variant_id]


def _get_payment_method(db: RetailDB, user_id: str, payment_method_id: str) -> PaymentMethod:
    user = _get_user(db, user_id)
    if payment_method_id not in user.payment_methods:
        raise ValueError("Payment method not found")
    return user.payment_methods[payment_method_id]


def _is_pending_order(order: Order) -> bool:
    return "pending" in order.status


# --- Tools (RetailTools public methods) -------------------------------------


@_action
def calculate(db: RetailDB, expression: str) -> str:
    if not all(char in "0123456789+-*/(). " for char in expression):
        raise ValueError("Invalid characters in expression")
    return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))


@_action
def cancel_pending_order(db: RetailDB, order_id: str, reason: str) -> Order:
    # check order exists and is pending
    order = _get_order(db, order_id)
    if order.status != "pending":
        raise ValueError("Non-pending order cannot be cancelled")

    # check reason
    if reason not in {"no longer needed", "ordered by mistake"}:
        raise ValueError("Invalid reason")

    # handle refund
    refunds = []
    for payment in order.payment_history:
        payment_id = payment.payment_method_id
        refund = OrderPayment(
            transaction_type="refund",
            amount=payment.amount,
            payment_method_id=payment_id,
        )
        refunds.append(refund)
        user = _get_user(db, order.user_id)
        payment_method = _get_payment_method(db, user.user_id, payment_id)
        if isinstance(payment_method, GiftCard):  # refund to gift card immediately
            payment_method.balance += payment.amount
            payment_method.balance = round(payment_method.balance, 2)

    # update order status
    order.status = "cancelled"
    order.cancel_reason = reason
    order.payment_history.extend(refunds)

    return order


@_action
def exchange_delivered_order_items(
    db: RetailDB,
    order_id: str,
    item_ids: List[str],
    new_item_ids: List[str],
    payment_method_id: str,
) -> Order:
    # check order exists and is delivered
    order = _get_order(db, order_id)
    if order.status != "delivered":
        raise ValueError("Non-delivered order cannot be exchanged")

    # check the items to be exchanged exist. There can be duplicate items in the list.
    all_item_ids = [item.item_id for item in order.items]
    for item_id in item_ids:
        if item_ids.count(item_id) > all_item_ids.count(item_id):
            raise ValueError(f"Number of {item_id} not found.")

    # check new items exist and match old items and are available
    if len(item_ids) != len(new_item_ids):
        raise ValueError("The number of items to be exchanged should match.")

    diff_price = 0
    for item_id, new_item_id in zip(item_ids, new_item_ids):
        item = next((item for item in order.items if item.item_id == item_id), None)
        if item is None:
            raise ValueError(f"Item {item_id} not found")
        product_id = item.product_id
        variant = _get_variant(db, product_id, new_item_id)
        if not variant.available:
            raise ValueError(f"New item {new_item_id} not found or available")

        old_price = item.price
        new_price = variant.price
        diff_price += new_price - old_price

    diff_price = round(diff_price, 2)

    # check payment method exists and can cover the price difference if gift card
    payment_method = _get_payment_method(db, order.user_id, payment_method_id)

    if isinstance(payment_method, GiftCard) and payment_method.balance < diff_price:
        raise ValueError("Insufficient gift card balance to pay for the price difference")

    # modify the order
    order.status = "exchange requested"
    order.exchange_items = sorted(item_ids)
    order.exchange_new_items = sorted(new_item_ids)
    order.exchange_payment_method_id = payment_method_id
    order.exchange_price_difference = diff_price

    return order


@_action
def find_user_id_by_name_zip(db: RetailDB, first_name: str, last_name: str, zip: str) -> str:
    for user_id, user in db.users.items():
        if (
            user.name.first_name.lower() == first_name.lower()
            and user.name.last_name.lower() == last_name.lower()
            and user.address.zip == zip
        ):
            return user_id
    raise ValueError("User not found")


@_action
def find_user_id_by_email(db: RetailDB, email: str) -> str:
    for user_id, user in db.users.items():
        if user.email.lower() == email.lower():
            return user_id
    raise ValueError("User not found")


@_action
def get_order_details(db: RetailDB, order_id: str) -> Order:
    return _get_order(db, order_id)


@_action
def get_product_details(db: RetailDB, product_id: str) -> Product:
    return _get_product(db, product_id)


@_action
def get_item_details(db: RetailDB, item_id: str) -> Variant:
    return _get_item(db, item_id)


@_action
def get_user_details(db: RetailDB, user_id: str) -> User:
    return _get_user(db, user_id)


@_action
def list_all_product_types(db: RetailDB) -> str:
    product_dict = {product.name: product.product_id for product in db.products.values()}
    return json.dumps(product_dict, sort_keys=True)


@_action
def modify_pending_order_address(
    db: RetailDB,
    order_id: str,
    address1: str,
    address2: str,
    city: str,
    state: str,
    country: str,
    zip: str,
) -> Order:
    # Check if the order exists and is pending
    order = _get_order(db, order_id)
    if not _is_pending_order(order):
        raise ValueError("Non-pending order cannot be modified")

    # Modify the address
    order.address = UserAddress(
        address1=address1,
        address2=address2,
        city=city,
        state=state,
        country=country,
        zip=zip,
    )
    return order


@_action
def modify_pending_order_items(
    db: RetailDB,
    order_id: str,
    item_ids: List[str],
    new_item_ids: List[str],
    payment_method_id: str,
) -> Order:
    # Check if the order exists and is pending
    order = _get_order(db, order_id)
    if order.status != "pending":
        raise ValueError("Non-pending order cannot be modified")

    # Check if the items to be modified exist. There can be duplicate items in the list.
    all_item_ids = [item.item_id for item in order.items]
    for item_id in item_ids:
        if item_ids.count(item_id) > all_item_ids.count(item_id):
            raise ValueError(f"{item_id} not found")

    # Check new items exist, match old items, and are available
    if len(item_ids) != len(new_item_ids):
        raise ValueError("The number of items to be exchanged should match")

    diff_price = 0
    for item_id, new_item_id in zip(item_ids, new_item_ids):
        if item_id == new_item_id:
            raise ValueError("The new item id should be different from the old item id")
        item = next((item for item in order.items if item.item_id == item_id), None)
        if item is None:
            raise ValueError(f"Item {item_id} not found")
        product_id = item.product_id
        variant = _get_variant(db, product_id, new_item_id)
        if not variant.available:
            raise ValueError(f"New item {new_item_id} not found or available")

        old_price = item.price
        new_price = variant.price
        diff_price += new_price - old_price

    # Check if the payment method exists
    payment_method = _get_payment_method(db, order.user_id, payment_method_id)

    # If the new item is more expensive, check if the gift card has enough balance
    if isinstance(payment_method, GiftCard) and payment_method.balance < diff_price:
        raise ValueError("Insufficient gift card balance to pay for the new item")

    # Handle the payment or refund
    order.payment_history.append(
        OrderPayment(
            transaction_type="payment" if diff_price > 0 else "refund",
            amount=abs(diff_price),
            payment_method_id=payment_method_id,
        )
    )
    if isinstance(payment_method, GiftCard):
        payment_method.balance -= diff_price
        payment_method.balance = round(payment_method.balance, 2)

    # Modify the order. As in tau2, every modified item takes the price and
    # options of the last variant looked up above.
    for item_id, new_item_id in zip(item_ids, new_item_ids):
        item = next((item for item in order.items if item.item_id == item_id), None)
        if item is None:
            raise ValueError(f"Item {item_id} not found")
        item.item_id = new_item_id
        item.price = variant.price
        item.options = variant.options
    order.status = "pending (item modified)"

    return order


@_action
def modify_pending_order_payment(db: RetailDB, order_id: str, payment_method_id: str) -> Order:
    order = _get_order(db, order_id)

    # Check if the order exists and is pending
    if not _is_pending_order(order):
        raise ValueError("Non-pending order cannot be modified")

    # Check if the payment method exists
    payment_method = _get_payment_method(db, order.user_id, payment_method_id)

    # Check that the payment history should only have one payment
    if len(order.payment_history) != 1 or order.payment_history[0].transaction_type != "payment":
        raise ValueError("There should be exactly one payment for a pending order")

    # Check that the payment method is different
    if order.payment_history[0].payment_method_id == payment_method_id:
        raise ValueError("The new payment method should be different from the current one")

    amount = order.payment_history[0].amount

    # Check if the new payment method has enough balance if it is a gift card
    if isinstance(payment_method, GiftCard) and payment_method.balance < amount:
        raise ValueError("Insufficient gift card balance to pay for the order")

    # Modify the payment method
    order.payment_history.extend(
        [
            OrderPayment(
                transaction_type="payment",
                amount=amount,
                payment_method_id=payment_method_id,
            ),
            OrderPayment(
                transaction_type="refund",
                amount=amount,
                payment_method_id=order.payment_history[0].payment_method_id,
            ),
        ]
    )

    # If payment is made by gift card, update the balance
    if isinstance(payment_method, GiftCard):
        payment_method.balance -= amount
        payment_method.balance = round(payment_method.balance, 2)

    # If refund is made to a gift card, update the balance
    old_payment_method = _get_payment_method(db, order.user_id, order.payment_history[0].payment_method_id)
    if isinstance(old_payment_method, GiftCard):
        old_payment_method.balance += amount
        old_payment_method.balance = round(old_payment_method.balance, 2)

    return order


@_action
def modify_user_address(
    db: RetailDB,
    user_id: str,
    address1: str,
    address2: str,
    city: str,
    state: str,
    country: str,
    zip: str,
) -> User:
    user = _get_user(db, user_id)
    user.address = UserAddress(
        address1=address1,
        address2=address2,
        city=city,
        state=state,
        country=country,
        zip=zip,
    )
    return user


@_action
def return_delivered_order_items(
    db: RetailDB, order_id: str, item_ids: List[str], payment_method_id: str
) -> Order:
    order = _get_order(db, order_id)
    if order.status != "delivered":
        raise ValueError("Non-delivered order cannot be returned")

    # Check if the payment method exists and is either the original payment method or a gift card
    user = _get_user(db, order.user_id)
    payment_method = _get_payment_method(db, user.user_id, payment_method_id)

    if (
        not isinstance(payment_method, GiftCard)
        and payment_method_id != order.payment_history[0].payment_method_id
    ):
        raise ValueError("Payment method should be the original payment method")

    # Check if the items to be returned exist (there could be duplicate items in either list)
    all_item_ids = [item.item_id for item in order.items]
    for item_id in item_ids:
        if item_ids.count(item_id) > all_item_ids.count(item_id):
            raise ValueError("Some item not found")

    # Update the order status
    order.status = "return requested"
    order.return_items = sorted(item_ids)
    order.return_payment_method_id = payment_method_id

    return order


@_action
def transfer_to_human_agents(db: RetailDB, summary: str) -> str:
    return "Transfer successful"


ACTIONS = {
    fn.__name__: fn
    for fn in [
        calculate,
        cancel_pending_order,
        exchange_delivered_order_items,
        find_user_id_by_email,
        find_user_id_by_name_zip,
        get_item_details,
        get_order_details,
        get_product_details,
        get_user_details,
        list_all_product_types,
        modify_pending_order_address,
        modify_pending_order_items,
        modify_pending_order_payment,
        modify_user_address,
        return_delivered_order_items,
        transfer_to_human_agents,
    ]
}

# tau2's ToolType for each tool: READ tools never change the database.
READ_ONLY = {
    "calculate",
    "find_user_id_by_email",
    "find_user_id_by_name_zip",
    "get_item_details",
    "get_order_details",
    "get_product_details",
    "get_user_details",
    "list_all_product_types",
}
