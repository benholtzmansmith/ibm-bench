"""watsonx Orchestrate ADK tools for the tau-bench airline domain.

Each tool keeps the name, parameters and description of the matching
tau-bench tool so evaluation goals can reference tau-bench's gold actions
directly. The logic lives in ``airline_logic``.

Import with the tools directory as the package root so the data files ship
with every tool:

    orchestrate tools import -k python -f airline/tools/airline_tools.py \
        -r airline/tools/requirements.txt -p airline/tools

The Orchestrate tool runtime does not share memory between invocations, so
every call starts from the pristine tau-bench database. A write is validated
and returned exactly as in tau-bench, but a later read in the same
conversation will not see it.
"""

from typing import List, Literal

from pydantic import BaseModel, Field

from ibm_watsonx_orchestrate.agent_builder.tools import ToolPermission, tool

import airline_logic

Cabin = Literal["basic_economy", "economy", "business"]


class FlightSegment(BaseModel):
    flight_number: str = Field(description="Flight number, such as 'HAT001'.")
    date: str = Field(
        description="The date for the flight in the format 'YYYY-MM-DD', such as '2024-05-01'."
    )


class Passenger(BaseModel):
    first_name: str = Field(description="The first name of the passenger, such as 'Noah'.")
    last_name: str = Field(description="The last name of the passenger, such as 'Brown'.")
    dob: str = Field(
        description="The date of birth of the passenger in the format 'YYYY-MM-DD', such as '1990-01-01'."
    )


class Payment(BaseModel):
    payment_id: str = Field(
        description="The payment id stored in user profile, such as 'credit_card_7815826', "
        "'gift_card_7815826', 'certificate_7815826'."
    )
    amount: float = Field(description="The amount to be paid.")


def _plain(items) -> list:
    """Tool arguments may arrive as pydantic models or dicts; tau-bench logic wants dicts."""
    out = []
    for item in items:
        d = item.model_dump() if isinstance(item, BaseModel) else dict(item)
        if isinstance(d.get("amount"), float) and d["amount"].is_integer():
            d["amount"] = int(d["amount"])
        out.append(d)
    return out


@tool(permission=ToolPermission.READ_WRITE)
def book_reservation(
    user_id: str,
    origin: str,
    destination: str,
    flight_type: Literal["one_way", "round_trip"],
    cabin: Cabin,
    flights: List[FlightSegment],
    passengers: List[Passenger],
    payment_methods: List[Payment],
    total_baggages: int,
    nonfree_baggages: int,
    insurance: Literal["yes", "no"],
) -> str:
    """Book a reservation.

    Args:
        user_id: The ID of the user to book the reservation, such as 'sara_doe_496'.
        origin: The IATA code for the origin city, such as 'SFO'.
        destination: The IATA code for the destination city, such as 'JFK'.
        flight_type: Either 'one_way' or 'round_trip'.
        cabin: One of 'basic_economy', 'economy' or 'business'.
        flights: An array of objects containing details about each piece of flight.
        passengers: An array of objects containing details about each passenger.
        payment_methods: An array of objects containing details about each payment method.
        total_baggages: The total number of baggage items included in the reservation.
        nonfree_baggages: The number of non-free baggage items included in the reservation.
        insurance: Either 'yes' or 'no'.

    Returns:
        The new reservation as JSON, or an error message.
    """
    return airline_logic.book_reservation(
        airline_logic.load_data(),
        user_id=user_id,
        origin=origin,
        destination=destination,
        flight_type=flight_type,
        cabin=cabin,
        flights=_plain(flights),
        passengers=_plain(passengers),
        payment_methods=_plain(payment_methods),
        total_baggages=total_baggages,
        nonfree_baggages=nonfree_baggages,
        insurance=insurance,
    )


@tool(permission=ToolPermission.READ_ONLY)
def calculate(expression: str) -> str:
    """Calculate the result of a mathematical expression.

    Args:
        expression: The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

    Returns:
        The result rounded to two decimals, or an error message.
    """
    return airline_logic.calculate({}, expression=expression)


@tool(permission=ToolPermission.READ_WRITE)
def cancel_reservation(reservation_id: str) -> str:
    """Cancel the whole reservation.

    Args:
        reservation_id: The reservation ID, such as 'ZFA04Y'.

    Returns:
        The cancelled reservation as JSON, or an error message.
    """
    return airline_logic.cancel_reservation(airline_logic.load_data(), reservation_id=reservation_id)


@tool(permission=ToolPermission.READ_ONLY)
def get_reservation_details(reservation_id: str) -> str:
    """Get the details of a reservation.

    Args:
        reservation_id: The reservation id, such as '8JX2WO'.

    Returns:
        The reservation as JSON, or an error message.
    """
    return airline_logic.get_reservation_details(airline_logic.load_data(), reservation_id=reservation_id)


@tool(permission=ToolPermission.READ_ONLY)
def get_user_details(user_id: str) -> str:
    """Get the details of an user, including their reservations.

    Args:
        user_id: The user id, such as 'sara_doe_496'.

    Returns:
        The user profile as JSON, or an error message.
    """
    return airline_logic.get_user_details(airline_logic.load_data(), user_id=user_id)


@tool(permission=ToolPermission.READ_ONLY)
def list_all_airports() -> str:
    """List all airports and their cities.

    Returns:
        A JSON object mapping IATA codes to city names.
    """
    return airline_logic.list_all_airports({})


@tool(permission=ToolPermission.READ_ONLY)
def search_direct_flight(origin: str, destination: str, date: str) -> str:
    """Search direct flights between two cities on a specific date.

    Args:
        origin: The origin city airport in three letters, such as 'JFK'.
        destination: The destination city airport in three letters, such as 'LAX'.
        date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-01-01'.

    Returns:
        A JSON list of available flights.
    """
    return airline_logic.search_direct_flight(
        airline_logic.load_data(), origin=origin, destination=destination, date=date
    )


@tool(permission=ToolPermission.READ_ONLY)
def search_onestop_flight(origin: str, destination: str, date: str) -> str:
    """Search direct flights between two cities on a specific date.

    Args:
        origin: The origin city airport in three letters, such as 'JFK'.
        destination: The destination city airport in three letters, such as 'LAX'.
        date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-05-01'.

    Returns:
        A JSON list of two-segment itineraries.
    """
    return airline_logic.search_onestop_flight(
        airline_logic.load_data(), origin=origin, destination=destination, date=date
    )


@tool(permission=ToolPermission.READ_WRITE)
def send_certificate(user_id: str, amount: int) -> str:
    """Send a certificate to a user. Be careful!

    Args:
        user_id: The ID of the user to book the reservation, such as 'sara_doe_496'.
        amount: Certificate amount to send.

    Returns:
        A confirmation message, or an error message.
    """
    return airline_logic.send_certificate(airline_logic.load_data(), user_id=user_id, amount=amount)


@tool(permission=ToolPermission.READ_ONLY)
def think(thought: str) -> str:
    """Use the tool to think about something. It will not obtain new information or change the database, but just append the thought to the log. Use it when complex reasoning is needed.

    Args:
        thought: A thought to think about.

    Returns:
        An empty string.
    """
    return airline_logic.think({}, thought=thought)


@tool(permission=ToolPermission.READ_ONLY)
def transfer_to_human_agents(summary: str) -> str:
    """Transfer the user to a human agent, with a summary of the user's issue. Only transfer if the user explicitly asks for a human agent, or if the user's issue cannot be resolved by the agent with the available tools.

    Args:
        summary: A summary of the user's issue.

    Returns:
        A confirmation that the transfer happened.
    """
    return airline_logic.transfer_to_human_agents({}, summary=summary)


@tool(permission=ToolPermission.READ_WRITE)
def update_reservation_baggages(
    reservation_id: str, total_baggages: int, nonfree_baggages: int, payment_id: str
) -> str:
    """Update the baggage information of a reservation.

    Args:
        reservation_id: The reservation ID, such as 'ZFA04Y'.
        total_baggages: The updated total number of baggage items included in the reservation.
        nonfree_baggages: The updated number of non-free baggage items included in the reservation.
        payment_id: The payment id stored in user profile, such as 'credit_card_7815826', 'gift_card_7815826', 'certificate_7815826'.

    Returns:
        The updated reservation as JSON, or an error message.
    """
    return airline_logic.update_reservation_baggages(
        airline_logic.load_data(),
        reservation_id=reservation_id,
        total_baggages=total_baggages,
        nonfree_baggages=nonfree_baggages,
        payment_id=payment_id,
    )


@tool(permission=ToolPermission.READ_WRITE)
def update_reservation_flights(
    reservation_id: str, cabin: Cabin, flights: List[FlightSegment], payment_id: str
) -> str:
    """Update the flight information of a reservation.

    Args:
        reservation_id: The reservation ID, such as 'ZFA04Y'.
        cabin: One of 'basic_economy', 'economy' or 'business'.
        flights: An array of objects containing details about each piece of flight in the ENTIRE new reservation. Even if the a flight segment is not changed, it should still be included in the array.
        payment_id: The payment id stored in user profile, such as 'credit_card_7815826', 'gift_card_7815826', 'certificate_7815826'.

    Returns:
        The updated reservation as JSON, or an error message.
    """
    return airline_logic.update_reservation_flights(
        airline_logic.load_data(),
        reservation_id=reservation_id,
        cabin=cabin,
        flights=_plain(flights),
        payment_id=payment_id,
    )


@tool(permission=ToolPermission.READ_WRITE)
def update_reservation_passengers(reservation_id: str, passengers: List[Passenger]) -> str:
    """Update the passenger information of a reservation.

    Args:
        reservation_id: The reservation ID, such as 'ZFA04Y'.
        passengers: An array of objects containing details about each passenger.

    Returns:
        The updated reservation as JSON, or an error message.
    """
    return airline_logic.update_reservation_passengers(
        airline_logic.load_data(), reservation_id=reservation_id, passengers=_plain(passengers)
    )
