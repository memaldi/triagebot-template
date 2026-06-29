import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app import classifier, db
from app.models import TicketCreate, TicketUpdate

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")

app = FastAPI(title="TriageBot")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tickets", status_code=201)
def create_ticket(payload: TicketCreate) -> dict:
    logger.debug("POST /tickets title=%.80s", payload.title)
    try:
        classification = classifier.classify_ticket(payload.title, payload.description)
    except Exception:
        classification = classifier.FALLBACK_CLASSIFICATION
    return db.create_ticket(
        title=payload.title,
        description=payload.description,
        category=classification["category"],
        priority=classification["priority"],
        tags=classification["tags"],
    )


@app.get("/tickets")
def list_tickets(
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> list:
    return db.list_tickets(category=category, priority=priority, status=status)


@app.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: int, payload: TicketUpdate) -> dict:
    updates = payload.model_dump(exclude_none=True)
    ticket = db.update_ticket(ticket_id, **updates)
    if ticket is None:
        logger.error("PATCH /tickets/%s — ticket not found", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.delete("/tickets/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: int) -> Response:
    deleted = db.delete_ticket(ticket_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return Response(status_code=204)


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_detail(request: Request, ticket_id: int) -> HTMLResponse:
    ticket = db.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return templates.TemplateResponse(
        "ticket_detail.html",
        {"request": request, "ticket": ticket},
    )


@app.get("/tickets-table", response_class=HTMLResponse)
def tickets_table(
    request: Request,
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> HTMLResponse:
    tickets = db.list_tickets(category=category, priority=priority, status=status)
    return templates.TemplateResponse(
        "_tickets_table.html",
        {"request": request, "tickets": tickets},
    )


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> HTMLResponse:
    tickets = db.list_tickets(category=category, priority=priority, status=status)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tickets": tickets,
            "category": category,
            "priority": priority,
            "status": status,
        },
    )
