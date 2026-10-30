from django.http import HttpResponse


def is_htmx(request):
    headers = request.headers
    return (
        headers.get("HX-Request") == "true"
        and headers.get("HX-Boosted") != "true"
        and headers.get("HX-History-Restore-Request") != "true"
    )


def htmx_redirect(url):
    response = HttpResponse("")
    response["HX-Redirect"] = url
    return response


def htmx_trigger(response, event):
    response["HX-Trigger"] = event
    return response
