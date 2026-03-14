from fastapi.routing import APIRoute

from app.main import app


def test_appointment_notes_router_registered_once():
    matching_routes = [
        route
        for route in app.router.routes
        if isinstance(route, APIRoute) and route.path == "/appointments/{appointment_id}/notes"
    ]

    assert len(matching_routes) == 1
    assert matching_routes[0].methods == {"GET"}
