from fastapi.routing import APIRoute

from app.main import app


def test_appointment_notes_router_registered_once():
    expected_routes = {
        "/appointments/{appointment_id}/notes": [("GET",), ("POST",)],
        "/appointments/{appointment_id}/notes/{note_id}": [("PATCH",)],
        "/appointments/{appointment_id}/notes/{note_id}/archive": [("POST",)],
        "/appointments/{appointment_id}/notes/{note_id}/restore": [("POST",)],
    }

    for path, expected_methods in expected_routes.items():
        matching_routes = [
            route
            for route in app.router.routes
            if isinstance(route, APIRoute) and route.path == path
        ]
        route_methods = sorted(tuple(sorted(route.methods)) for route in matching_routes)

        assert len(matching_routes) == len(expected_methods)
        assert route_methods == expected_methods
