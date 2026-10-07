"""watsonx Orchestrate ADK tools for the tau2-bench retail domain.

Each tool keeps the name, parameters and description of the matching tau2
tool so evaluation goals can reference tau2's gold actions directly. The logic
lives in ``retail_logic``.

Import with the tools directory as the package root so the database ships
with every tool:

    orchestrate tools import -k python -f retail/tools/retail_tools.py \
        -r retail/tools/requirements.txt -p retail/tools

The Orchestrate tool runtime does not share memory between invocations, so
every call starts from the pristine tau2 database. A write is validated and
returned exactly as in tau2, but a later read in the same conversation will
not see it.
"""

from typing import List

from ibm_watsonx_orchestrate.agent_builder.tools import ToolPermission, tool

import retail_logic


@tool(permission=ToolPermission.READ_ONLY)
def calculate(expression: str) -> str:
    """Calculate the result of a mathematical expression.

    Args:
        expression: The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

    Returns:
        The result of the mathematical expression, or an error message.
    """
    return retail_logic.calculate(None, expression=expression)


@tool(permission=ToolPermission.READ_WRITE)
def cancel_pending_order(order_id: str, reason: str) -> str:
    """Cancel a pending order. If the order is already processed or delivered, it cannot be cancelled. The agent needs to explain the cancellation detail and ask for explicit user confirmation (yes/no) to proceed. If the user confirms, the order status will be changed to 'cancelled' and the payment will be refunded. The refund will be added to the user's gift card balance immediately if the payment was made using a gift card, otherwise the refund would take 5-7 business days to process. The function returns the order details after the cancellation.

    Args:
        order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
        reason: The reason for cancellation, which should be either 'no longer needed' or 'ordered by mistake'.

    Returns:
        The order details after the cancellation as JSON, or an error message.
    """
    return retail_logic.cancel_pending_order(retail_logic.load_data(), order_id=order_id, reason=reason)


@tool(permission=ToolPermission.READ_WRITE)
def exchange_delivered_order_items(
    order_id: str, item_ids: List[str], new_item_ids: List[str], payment_method_id: str
) -> str:
    """Exchange items in a delivered order to new items of the same product type. For a delivered order, return or exchange can be only done once by the agent. The agent needs to explain the exchange detail and ask for explicit user confirmation (yes/no) to proceed.

    Args:
        order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
        item_ids: The item ids to be exchanged, each such as '1008292230'. There could be duplicate items in the list.
        new_item_ids: The item ids to be exchanged for, each such as '1008292230'. There could be duplicate items in the list. Each new item id should match the item id in the same position and be of the same product.
        payment_method_id: The payment method id to pay or receive refund for the item price difference, such as 'gift_card_0000000' or 'credit_card_0000000'. These can be looked up from the user or order details.

    Returns:
        The order details after the exchange as JSON, or an error message.
    """
    return retail_logic.exchange_delivered_order_items(
        retail_logic.load_data(),
        order_id=order_id,
        item_ids=list(item_ids),
        new_item_ids=list(new_item_ids),
        payment_method_id=payment_method_id,
    )


@tool(permission=ToolPermission.READ_ONLY)
def find_user_id_by_email(email: str) -> str:
    """Find user id by email. If the user is not found, the function will return an error message.

    Args:
        email: The email of the user, such as 'something@example.com'.

    Returns:
        The user id if found, otherwise an error message.
    """
    return retail_logic.find_user_id_by_email(retail_logic.load_data(), email=email)


@tool(permission=ToolPermission.READ_ONLY)
def find_user_id_by_name_zip(first_name: str, last_name: str, zip: str) -> str:
    """Find user id by first name, last name, and zip code. If the user is not found, the function will return an error message. By default, find user id by email, and only call this function if the user is not found by email or cannot remember email.

    Args:
        first_name: The first name of the customer, such as 'John'.
        last_name: The last name of the customer, such as 'Doe'.
        zip: The zip code of the customer, such as '12345'.

    Returns:
        The user id if found, otherwise an error message.
    """
    return retail_logic.find_user_id_by_name_zip(
        retail_logic.load_data(), first_name=first_name, last_name=last_name, zip=zip
    )


@tool(permission=ToolPermission.READ_ONLY)
def get_item_details(item_id: str) -> str:
    """Get the inventory details of an item.

    Args:
        item_id: The item id, such as '6086499569'. Be careful the item id is different from the product id.

    Returns:
        The item details as JSON, or an error message.
    """
    return retail_logic.get_item_details(retail_logic.load_data(), item_id=item_id)


@tool(permission=ToolPermission.READ_ONLY)
def get_order_details(order_id: str) -> str:
    """Get the status and details of an order.

    Args:
        order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.

    Returns:
        The order details as JSON, or an error message.
    """
    return retail_logic.get_order_details(retail_logic.load_data(), order_id=order_id)


@tool(permission=ToolPermission.READ_ONLY)
def get_product_details(product_id: str) -> str:
    """Get the inventory details of a product.

    Args:
        product_id: The product id, such as '6086499569'. Be careful the product id is different from the item id.

    Returns:
        The product details as JSON, or an error message.
    """
    return retail_logic.get_product_details(retail_logic.load_data(), product_id=product_id)


@tool(permission=ToolPermission.READ_ONLY)
def get_user_details(user_id: str) -> str:
    """Get the details of a user, including their orders.

    Args:
        user_id: The user id, such as 'sara_doe_496'.

    Returns:
        The user details as JSON, or an error message.
    """
    return retail_logic.get_user_details(retail_logic.load_data(), user_id=user_id)


@tool(permission=ToolPermission.READ_ONLY)
def list_all_product_types() -> str:
    """List the name and product id of all product types. Each product type has a variety of different items with unique item ids and options. There are only 50 product types in the store.

    Returns:
        A JSON string mapping product names to their product IDs, sorted alphabetically by name.
    """
    return retail_logic.list_all_product_types(retail_logic.load_data())


@tool(permission=ToolPermission.READ_WRITE)
def modify_pending_order_address(
    order_id: str, address1: str, address2: str, city: str, state: str, country: str, zip: str
) -> str:
    """Modify the shipping address of a pending order. The agent needs to explain the modification detail and ask for explicit user confirmation (yes/no) to proceed.

    Args:
        order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
        address1: The first line of the address, such as '123 Main St'.
        address2: The second line of the address, such as 'Apt 1' or ''.
        city: The city, such as 'San Francisco'.
        state: The state, such as 'CA'.
        country: The country, such as 'USA'.
        zip: The zip code, such as '12345'.

    Returns:
        The order details after the modification as JSON, or an error message.
    """
    return retail_logic.modify_pending_order_address(
        retail_logic.load_data(),
        order_id=order_id,
        address1=address1,
        address2=address2,
        city=city,
        state=state,
        country=country,
        zip=zip,
    )


@tool(permission=ToolPermission.READ_WRITE)
def modify_pending_order_items(
    order_id: str, item_ids: List[str], new_item_ids: List[str], payment_method_id: str
) -> str:
    """Modify items in a pending order to new items of the same product type. For a pending order, this function can only be called once. The agent needs to explain the exchange detail and ask for explicit user confirmation (yes/no) to proceed.

    Args:
        order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
        item_ids: The item ids to be modified, each such as '1008292230'. There could be duplicate items in the list.
        new_item_ids: The item ids to be modified for, each such as '1008292230'. There could be duplicate items in the list. Each new item id should match the item id in the same position and be of the same product.
        payment_method_id: The payment method id to pay or receive refund for the item price difference, such as 'gift_card_0000000' or 'credit_card_0000000'. These can be looked up from the user or order details.

    Returns:
        The order details after the modification as JSON, or an error message.
    """
    return retail_logic.modify_pending_order_items(
        retail_logic.load_data(),
        order_id=order_id,
        item_ids=list(item_ids),
        new_item_ids=list(new_item_ids),
        payment_method_id=payment_method_id,
    )


@tool(permission=ToolPermission.READ_WRITE)
def modify_pending_order_payment(order_id: str, payment_method_id: str) -> str:
    """Modify the payment method of a pending order. The agent needs to explain the modification detail and ask for explicit user confirmation (yes/no) to proceed.

    Args:
        order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
        payment_method_id: The payment method id to pay or receive refund for the item price difference, such as 'gift_card_0000000' or 'credit_card_0000000'. These can be looked up from the user or order details.

    Returns:
        The order details after the modification as JSON, or an error message.
    """
    return retail_logic.modify_pending_order_payment(
        retail_logic.load_data(), order_id=order_id, payment_method_id=payment_method_id
    )


@tool(permission=ToolPermission.READ_WRITE)
def modify_user_address(
    user_id: str, address1: str, address2: str, city: str, state: str, country: str, zip: str
) -> str:
    """Modify the default address of a user. The agent needs to explain the modification detail and ask for explicit user confirmation (yes/no) to proceed.

    Args:
        user_id: The user id, such as 'sara_doe_496'.
        address1: The first line of the address, such as '123 Main St'.
        address2: The second line of the address, such as 'Apt 1' or ''.
        city: The city, such as 'San Francisco'.
        state: The state, such as 'CA'.
        country: The country, such as 'USA'.
        zip: The zip code, such as '12345'.

    Returns:
        The user details after the modification as JSON, or an error message.
    """
    return retail_logic.modify_user_address(
        retail_logic.load_data(),
        user_id=user_id,
        address1=address1,
        address2=address2,
        city=city,
        state=state,
        country=country,
        zip=zip,
    )


@tool(permission=ToolPermission.READ_WRITE)
def return_delivered_order_items(order_id: str, item_ids: List[str], payment_method_id: str) -> str:
    """Return some items of a delivered order. The order status will be changed to 'return requested'. The agent needs to explain the return detail and ask for explicit user confirmation (yes/no) to proceed. The user will receive follow-up email for how and where to return the item.

    Args:
        order_id: The order id, such as '#W0000000'. Be careful there is a '#' symbol at the beginning of the order id.
        item_ids: The item ids to be returned, each such as '1008292230'. There could be duplicate items in the list.
        payment_method_id: The payment method id to pay or receive refund for the item price difference, such as 'gift_card_0000000' or 'credit_card_0000000'. These can be looked up from the user or order details.

    Returns:
        The order details after requesting the return as JSON, or an error message.
    """
    return retail_logic.return_delivered_order_items(
        retail_logic.load_data(),
        order_id=order_id,
        item_ids=list(item_ids),
        payment_method_id=payment_method_id,
    )


@tool(permission=ToolPermission.READ_ONLY)
def transfer_to_human_agents(summary: str) -> str:
    """Transfer the user to a human agent, with a summary of the user's issue. Only transfer if the user explicitly asks for a human agent, or given the policy and the available tools, you cannot solve the user's issue.

    Args:
        summary: A summary of the user's issue.

    Returns:
        A message indicating the user has been transferred to a human agent.
    """
    return retail_logic.transfer_to_human_agents(None, summary=summary)
