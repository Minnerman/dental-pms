from fastapi.routing import APIRoute

from app.main import app


def test_appointment_notes_router_registered_once():
    matching_routes = [
        route
        for route in app.router.routes
        if isinstance(route, APIRoute) and route.path == "/appointments/{appointment_id}/notes"
    ]

    route_methods = sorted(tuple(sorted(route.methods)) for route in matching_routes)

    assert len(matching_routes) == 2
    assert route_methods == [("GET",), ("POST",)]
