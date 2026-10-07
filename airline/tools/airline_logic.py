"""Business logic for the tau-bench airline domain.

Ported from sierra-research/tau-bench (tau_bench/envs/airline/tools, MIT
license, see airline/source/TAU_BENCH_LICENSE.txt). Each function takes the
in-memory database dict (``{"flights", "reservations", "users"}``), mutates
it the same way the original tool did, and returns the same string the
original tool returned. Keeping this module free of ADK imports lets the
offline tests replay tau-bench's gold actions without an Orchestrate server.
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(__file__).parent / "data"


def load_data() -> Dict[str, Any]:
    with open(DATA_DIR / "flights.json") as f:
        flights = json.load(f)
    with open(DATA_DIR / "reservations.json") as f:
        reservations = json.load(f)
    with open(DATA_DIR / "users.json") as f:
        users = json.load(f)
    return {"flights": flights, "reservations": reservations, "users": users}


def book_reservation(
    data: Dict[str, Any],
    user_id: str,
    origin: str,
    destination: str,
    flight_type: str,
    cabin: str,
    flights: List[Dict[str, Any]],
    passengers: List[Dict[str, Any]],
    payment_methods: List[Dict[str, Any]],
    total_baggages: int,
    nonfree_baggages: int,
    insurance: str,
) -> str:
    reservations, users = data["reservations"], data["users"]
    if user_id not in users:
        return "Error: user not found"
    user = users[user_id]

    # assume each task makes at most 3 reservations
    reservation_id = "HATHAT"
    if reservation_id in reservations:
        reservation_id = "HATHAU"
        if reservation_id in reservations:
            reservation_id = "HATHAV"

    reservation = {
        "reservation_id": reservation_id,
        "user_id": user_id,
        "origin": origin,
        "destination": destination,
        "flight_type": flight_type,
        "cabin": cabin,
        "flights": deepcopy(flights),
        "passengers": passengers,
        "payment_history": payment_methods,
        "created_at": "2024-05-15T15:00:00",
        "total_baggages": total_baggages,
        "nonfree_baggages": nonfree_baggages,
        "insurance": insurance,
    }

    # update flights and calculate price
    total_price = 0
    for flight in reservation["flights"]:
        flight_number = flight["flight_number"]
        if flight_number not in data["flights"]:
            return f"Error: flight {flight_number} not found"
        flight_data = data["flights"][flight_number]
        if flight["date"] not in flight_data["dates"]:
            return f"Error: flight {flight_number} not found on date {flight['date']}"
        flight_date_data = flight_data["dates"][flight["date"]]
        if flight_date_data["status"] != "available":
            return f"Error: flight {flight_number} not available on date {flight['date']}"
        if flight_date_data["available_seats"][cabin] < len(passengers):
            return f"Error: not enough seats on flight {flight_number}"
        flight["price"] = flight_date_data["prices"][cabin]
        flight["origin"] = flight_data["origin"]
        flight["destination"] = flight_data["destination"]
        total_price += flight["price"] * len(passengers)

    if insurance == "yes":
        total_price += 30 * len(passengers)

    total_price += 50 * nonfree_baggages

    for payment_method in payment_methods:
        payment_id = payment_method["payment_id"]
        amount = payment_method["amount"]
        if payment_id not in user["payment_methods"]:
            return f"Error: payment method {payment_id} not found"
        if user["payment_methods"][payment_id]["source"] in ["gift_card", "certificate"]:
            if user["payment_methods"][payment_id]["amount"] < amount:
                return f"Error: not enough balance in payment method {payment_id}"
    if sum(payment["amount"] for payment in payment_methods) != total_price:
        return (
            f"Error: payment amount does not add up, total price is {total_price}, "
            f"but paid {sum(payment['amount'] for payment in payment_methods)}"
        )

    # if checks pass, deduct payment and update seats
    for payment_method in payment_methods:
        payment_id = payment_method["payment_id"]
        amount = payment_method["amount"]
        if user["payment_methods"][payment_id]["source"] == "gift_card":
            user["payment_methods"][payment_id]["amount"] -= amount
        elif user["payment_methods"][payment_id]["source"] == "certificate":
            del user["payment_methods"][payment_id]

    reservations[reservation_id] = reservation
    user["reservations"].append(reservation_id)
    return json.dumps(reservation)


def calculate(data: Dict[str, Any], expression: str) -> str:
    if not all(char in "0123456789+-*/(). " for char in expression):
        return "Error: invalid characters in expression"
    try:
        return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))
    except Exception as e:
        return f"Error: {e}"


def cancel_reservation(data: Dict[str, Any], reservation_id: str) -> str:
    reservations = data["reservations"]
    if reservation_id not in reservations:
        return "Error: reservation not found"
    reservation = reservations[reservation_id]

    # reverse the payment
    refunds = []
    for payment in reservation["payment_history"]:
        refunds.append({"payment_id": payment["payment_id"], "amount": -payment["amount"]})
    reservation["payment_history"].extend(refunds)
    reservation["status"] = "cancelled"
    return json.dumps(reservation)


def get_reservation_details(data: Dict[str, Any], reservation_id: str) -> str:
    reservations = data["reservations"]
    if reservation_id in reservations:
        return json.dumps(reservations[reservation_id])
    return "Error: user not found"


def get_user_details(data: Dict[str, Any], user_id: str) -> str:
    users = data["users"]
    if user_id in users:
        return json.dumps(users[user_id])
    return "Error: user not found"


AIRPORTS = {
    "SFO": "San Francisco",
    "JFK": "New York",
    "LAX": "Los Angeles",
    "ORD": "Chicago",
    "DFW": "Dallas",
    "DEN": "Denver",
    "SEA": "Seattle",
    "ATL": "Atlanta",
    "MIA": "Miami",
    "BOS": "Boston",
    "PHX": "Phoenix",
    "IAH": "Houston",
    "LAS": "Las Vegas",
    "MCO": "Orlando",
    "EWR": "Newark",
    "CLT": "Charlotte",
    "MSP": "Minneapolis",
    "DTW": "Detroit",
    "PHL": "Philadelphia",
    "LGA": "LaGuardia",
}


def list_all_airports(data: Dict[str, Any]) -> str:
    return json.dumps(AIRPORTS)


def search_direct_flight(data: Dict[str, Any], origin: str, destination: str, date: str) -> str:
    flights = data["flights"]
    results = []
    for flight in flights.values():
        if flight["origin"] == origin and flight["destination"] == destination:
            if date in flight["dates"] and flight["dates"][date]["status"] == "available":
                # results add flight except dates, but add flight["datas"][date]
                results.append({k: v for k, v in flight.items() if k != "dates"})
                results[-1].update(flight["dates"][date])
    return json.dumps(results)


def search_onestop_flight(data: Dict[str, Any], origin: str, destination: str, date: str) -> str:
    flights = data["flights"]
    results = []
    for flight1 in flights.values():
        if flight1["origin"] == origin:
            for flight2 in flights.values():
                if flight2["destination"] == destination and flight1["destination"] == flight2["origin"]:
                    date2 = (
                        f"2024-05-{int(date[-2:])+1}"
                        if "+1" in flight1["scheduled_arrival_time_est"]
                        else date
                    )
                    if flight1["scheduled_arrival_time_est"] > flight2["scheduled_departure_time_est"]:
                        continue
                    if date in flight1["dates"] and date2 in flight2["dates"]:
                        if (
                            flight1["dates"][date]["status"] == "available"
                            and flight2["dates"][date2]["status"] == "available"
                        ):
                            result1 = {k: v for k, v in flight1.items() if k != "dates"}
                            result1.update(flight1["dates"][date])
                            result1["date"] = date
                            result2 = {k: v for k, v in flight2.items() if k != "dates"}
                            result2.update(flight2["dates"][date])
                            result2["date"] = date2
                            results.append([result1, result2])
    return json.dumps(results)


def send_certificate(data: Dict[str, Any], user_id: str, amount: int) -> str:
    users = data["users"]
    if user_id not in users:
        return "Error: user not found"
    user = users[user_id]

    # add a certificate, assume at most 3 cases per task
    for id in [3221322, 3221323, 3221324]:
        payment_id = f"certificate_{id}"
        if payment_id not in user["payment_methods"]:
            user["payment_methods"][payment_id] = {
                "source": "certificate",
                "amount": amount,
                "id": payment_id,
            }
            return f"Certificate {payment_id} added to user {user_id} with amount {amount}."


def think(data: Dict[str, Any], thought: str) -> str:
    return ""


def transfer_to_human_agents(data: Dict[str, Any], summary: str) -> str:
    return "Transfer successful"


def update_reservation_baggages(
    data: Dict[str, Any],
    reservation_id: str,
    total_baggages: int,
    nonfree_baggages: int,
    payment_id: str,
) -> str:
    users, reservations = data["users"], data["reservations"]
    if reservation_id not in reservations:
        return "Error: reservation not found"
    reservation = reservations[reservation_id]

    total_price = 50 * max(0, nonfree_baggages - reservation["nonfree_baggages"])
    if payment_id not in users[reservation["user_id"]]["payment_methods"]:
        return "Error: payment method not found"
    payment_method = users[reservation["user_id"]]["payment_methods"][payment_id]
    if payment_method["source"] == "certificate":
        return "Error: certificate cannot be used to update reservation"
    elif payment_method["source"] == "gift_card" and payment_method["amount"] < total_price:
        return "Error: gift card balance is not enough"

    reservation["total_baggages"] = total_baggages
    reservation["nonfree_baggages"] = nonfree_baggages
    if payment_method["source"] == "gift_card":
        payment_method["amount"] -= total_price

    if total_price != 0:
        reservation["payment_history"].append({"payment_id": payment_id, "amount": total_price})

    return json.dumps(reservation)


def update_reservation_flights(
    data: Dict[str, Any],
    reservation_id: str,
    cabin: str,
    flights: List[Dict[str, Any]],
    payment_id: str,
) -> str:
    users, reservations = data["users"], data["reservations"]
    if reservation_id not in reservations:
        return "Error: reservation not found"
    reservation = reservations[reservation_id]

    # update flights and calculate price
    total_price = 0
    flights = deepcopy(flights)
    for flight in flights:
        # if existing flight, ignore
        if _ := [
            f
            for f in reservation["flights"]
            if f["flight_number"] == flight["flight_number"]
            and f["date"] == flight["date"]
            and cabin == reservation["cabin"]
        ]:
            total_price += _[0]["price"] * len(reservation["passengers"])
            flight["price"] = _[0]["price"]
            flight["origin"] = _[0]["origin"]
            flight["destination"] = _[0]["destination"]
            continue
        flight_number = flight["flight_number"]
        if flight_number not in data["flights"]:
            return f"Error: flight {flight_number} not found"
        flight_data = data["flights"][flight_number]
        if flight["date"] not in flight_data["dates"]:
            return f"Error: flight {flight_number} not found on date {flight['date']}"
        flight_date_data = flight_data["dates"][flight["date"]]
        if flight_date_data["status"] != "available":
            return f"Error: flight {flight_number} not available on date {flight['date']}"
        if flight_date_data["available_seats"][cabin] < len(reservation["passengers"]):
            return f"Error: not enough seats on flight {flight_number}"
        flight["price"] = flight_date_data["prices"][cabin]
        flight["origin"] = flight_data["origin"]
        flight["destination"] = flight_data["destination"]
        total_price += flight["price"] * len(reservation["passengers"])

    total_price -= sum(flight["price"] for flight in reservation["flights"]) * len(
        reservation["passengers"]
    )

    # check payment
    if payment_id not in users[reservation["user_id"]]["payment_methods"]:
        return "Error: payment method not found"
    payment_method = users[reservation["user_id"]]["payment_methods"][payment_id]
    if payment_method["source"] == "certificate":
        return "Error: certificate cannot be used to update reservation"
    elif payment_method["source"] == "gift_card" and payment_method["amount"] < total_price:
        return "Error: gift card balance is not enough"

    # if checks pass, deduct payment and update seats
    if payment_method["source"] == "gift_card":
        payment_method["amount"] -= total_price
    reservation["flights"] = flights
    if total_price != 0:
        reservation["payment_history"].append({"payment_id": payment_id, "amount": total_price})
    # do not make flight database update here, assume it takes time to be updated
    return json.dumps(reservation)


def update_reservation_passengers(
    data: Dict[str, Any], reservation_id: str, passengers: List[Dict[str, Any]]
) -> str:
    reservations = data["reservations"]
    if reservation_id not in reservations:
        return "Error: reservation not found"
    reservation = reservations[reservation_id]
    if len(passengers) != len(reservation["passengers"]):
        return "Error: number of passengers does not match"
    reservation["passengers"] = passengers
    return json.dumps(reservation)


ACTIONS = {
    fn.__name__: fn
    for fn in [
        book_reservation,
        calculate,
        cancel_reservation,
        get_reservation_details,
        get_user_details,
        list_all_airports,
        search_direct_flight,
        search_onestop_flight,
        send_certificate,
        think,
        transfer_to_human_agents,
        update_reservation_baggages,
        update_reservation_flights,
        update_reservation_passengers,
    ]
}
