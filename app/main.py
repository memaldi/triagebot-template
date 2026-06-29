import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app import auth, classifier, db
from app.models import LoginRequest, TicketCreate, TicketUpdate

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")

app = FastAPI(title="TriageBot")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/login")
def login(payload: LoginRequest) -> RedirectResponse:
    if not auth.validate_credentials(payload.username, payload.password):
        logger.warning("Failed login attempt for user: %s", payload.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("session_user", payload.username, httponly=True)
    logger.info("User logged in: %s", payload.username)
    return response


@app.get("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_user")
    return response


@app.post("/tickets", status_code=201)
def create_ticket(request: Request, payload: TicketCreate) -> dict:
    author = auth.get_current_user(request) or "anonymous"
    logger.debug("POST /tickets title=%.80s author=%s", payload.title, author)
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
        author=author,
    )


@app.get("/tickets")
def list_tickets(
    request: Request,
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> list:
    current_user = auth.get_current_user(request)
    viewer = current_user or "anonymous"
    author = None if auth.is_admin(viewer) else viewer
    return db.list_tickets(category=category, priority=priority, status=status, author=author)


@app.patch("/tickets/{ticket_id}")
def update_ticket(request: Request, ticket_id: int, payload: TicketUpdate) -> dict:
    current_user = auth.get_current_user(request) or "anonymous"
    ticket = db.get_ticket(ticket_id)
    if ticket is None:
        logger.error("PATCH /tickets/%s — ticket not found", ticket_id)
        raise HTTPException(status_code=404, detail="Ticket not found")
    auth.require_owner_or_admin(ticket["author"], current_user)
    updates = payload.model_dump(exclude_none=True)
    updated = db.update_ticket(ticket_id, **updates)
    return updated


@app.delete("/tickets/{ticket_id}", status_code=204)
def delete_ticket(request: Request, ticket_id: int) -> Response:
    current_user = auth.get_current_user(request) or "anonymous"
    ticket = db.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    auth.require_owner_or_admin(ticket["author"], current_user)
    db.delete_ticket(ticket_id)
    return Response(status_code=204)


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_detail(request: Request, ticket_id: int) -> HTMLResponse:
    current_user = auth.get_current_user(request) or "anonymous"
    ticket = db.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    auth.require_owner_or_admin(ticket["author"], current_user)
    can_manage = current_user == ticket["author"] or auth.is_admin(current_user)
    return templates.TemplateResponse(
        "ticket_detail.html",
        {
            "request": request,
            "ticket": ticket,
            "current_user": current_user,
            "can_manage": can_manage,
        },
    )


@app.get("/tickets-table", response_class=HTMLResponse)
def tickets_table(
    request: Request,
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> HTMLResponse:
    current_user = auth.get_current_user(request)
    viewer = current_user or "anonymous"
    author = None if auth.is_admin(viewer) else viewer
    tickets = db.list_tickets(category=category, priority=priority, status=status, author=author)
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
    current_user = auth.get_current_user(request)
    viewer = current_user or "anonymous"
    author = None if auth.is_admin(viewer) else viewer
    tickets = db.list_tickets(category=category, priority=priority, status=status, author=author)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tickets": tickets,
            "category": category,
            "priority": priority,
            "status": status,
            "current_user": current_user,
        },
    )
