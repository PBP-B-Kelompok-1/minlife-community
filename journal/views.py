import calendar
import html
import json
import re
from datetime import date

import nh3
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import JournalEntry

MONTHS = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]
MONTHS_SHORT = [
    "", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
]
WEEKDAYS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]

ALLOWED_TAGS = {"p", "br", "div", "b", "strong", "i", "em", "u", "ul", "ol", "li", "blockquote"}
MAX_LENGTH = 50000


def parse_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise Http404
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise Http404


def clean_html(raw):
    return nh3.clean(raw, tags=ALLOWED_TAGS, attributes={})


def plain_text(raw):
    spaced = re.sub(r"</(p|div|li|blockquote)>|<br\s*/?>", " ", raw, flags=re.I)
    text = html.unescape(nh3.clean(spaced, tags=set()))
    return " ".join(text.split())


def entry_data(entry):
    text = plain_text(entry.content)
    local = timezone.localtime(entry.updated_at)
    return {
        "date": entry.date.isoformat(),
        "snippet": text if len(text) <= 140 else text[:137].rstrip() + "...",
        "visibility": entry.visibility,
        "updated": f"{local.day} {MONTHS_SHORT[local.month]}, {local:%H:%M}",
    }


def entry_detail_data(day, entry):
    if entry is None:
        return {"date": day.isoformat(), "exists": False, "content": "", "visibility": "private"}
    return {**entry_data(entry), "exists": True, "content": entry.content}


def read_month(request, today):
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if not 1900 <= year <= 2200:
            raise ValueError
        date(year, month, 1)
    except ValueError:
        return today.year, today.month
    return year, month


def shift_month(year, month, step):
    index = year * 12 + (month - 1) + step
    return {"year": index // 12, "month": index % 12 + 1}


@login_required
def show_journal(request):
    today = timezone.localdate()
    year, month = read_month(request, today)

    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    start, end = weeks[0][0], weeks[-1][-1]

    # cuma ambil entry yang kelihatan di grid bulan ini
    rows = JournalEntry.objects.filter(user=request.user, date__range=(start, end))
    entries = {e.date.isoformat(): entry_data(e) for e in rows}

    grid = [
        [
            {
                "iso": d.isoformat(),
                "day": d.day,
                "in_month": d.month == month,
                "is_today": d == today,
                "has_entry": d.isoformat() in entries,
            }
            for d in week
        ]
        for week in weeks
    ]

    return render(request, "journal/calendar.html", {
        "weeks": grid,
        "weekdays": WEEKDAYS,
        "entries": entries,
        "year": year,
        "month": month,
        "month_name": MONTHS[month],
        "today": today.isoformat(),
        "prev": shift_month(year, month, -1),
        "next": shift_month(year, month, 1),
        "this_month": {"year": today.year, "month": today.month},
    })


@require_http_methods(["GET", "POST", "DELETE"])
def entry_detail(request, date_str):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sesi habis, silakan login lagi."}, status=401)

    day = parse_date(date_str)
    entry = JournalEntry.objects.filter(user=request.user, date=day).first()

    if request.method == "GET":
        return JsonResponse(entry_detail_data(day, entry))

    if request.method == "DELETE":
        if entry is None:
            return JsonResponse({"error": "Entry tidak ditemukan."}, status=404)
        entry.delete()
        return JsonResponse(entry_detail_data(day, None))

    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Data tidak valid."}, status=400)

    content = payload.get("content", "")
    visibility = payload.get("visibility", "private")
    if not isinstance(content, str) or visibility not in JournalEntry.Visibility.values:
        return JsonResponse({"error": "Data tidak valid."}, status=400)
    if len(content) > MAX_LENGTH:
        return JsonResponse({"error": "Entry terlalu panjang."}, status=400)

    content = clean_html(content)
    if not plain_text(content):
        return JsonResponse({"error": "Isi entry tidak boleh kosong."}, status=400)

    entry, created = JournalEntry.objects.update_or_create(
        user=request.user,
        date=day,
        defaults={"content": content, "visibility": visibility},
    )
    return JsonResponse(entry_detail_data(day, entry), status=201 if created else 200)
