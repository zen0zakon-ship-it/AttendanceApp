# main.py
from datetime import date
from math import radians, sin, cos, sqrt, atan2
import random
import uuid
from typing import Optional

from fastapi import FastAPI, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from database import Base, engine, get_db
from models import Student, Attendance, Admin

app = FastAPI()

# создаём таблицы
Base.metadata.create_all(bind=engine)

# статика и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --------- ГЕОЗОНА КОЛЛЕДЖА ---------
COLLEGE_LAT = 45.01
COLLEGE_LON = 78.22
ALLOWED_RADIUS_METERS = 400  # радиус вокруг колледжа в метрах


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


# --------- ЯЗЫК ---------
def get_lang(request: Request) -> str:
    lang = request.cookies.get("lang")
    if lang in ("ru", "kk"):
        return lang
    return "ru"


@app.get("/set-lang/{lang_code}")
def set_language(lang_code: str, request: Request):
    if lang_code not in ("ru", "kk"):
        lang_code = "ru"

    referer = request.headers.get("referer") or "/"
    response = RedirectResponse(url=referer, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="lang",
        value=lang_code,
        max_age=60 * 60 * 24 * 365,
        samesite="lax",
    )
    return response


def is_mobile_request(request: Request) -> bool:
    ua = (request.headers.get("user-agent") or "").lower()
    return any(x in ua for x in ["iphone", "android", "ipad", "mobile"])


# --------- ВСПОМОГАТЕЛЬНЫЕ ---------
def ensure_admin(db: Session):
    admin = db.query(Admin).filter(Admin.username == "admin").first()
    if not admin:
        admin = Admin(username="admin", password="admin123")
        db.add(admin)
        db.commit()


def generate_device_uid() -> str:
    return str(uuid.uuid4())


def generate_motivation_text(student: Student, lang: str) -> str:
    if lang == "kk":
        phrases = [
            f"{student.full_name}, тамаша бастама! Бүгінгі күніңіз сәтті өтсін!",
            "Жарайсың! Әр күн — жаңа мүмкіндік.",
            "Келгенің өте жақсы! Білімге жасаған қадамың зая кетпейді.",
            "Өзіңе сен! Қазірден бастап болашағыңды құрып жатырсың.",
        ]
    else:
        phrases = [
            f"{student.full_name}, отличный старт! Пусть день пройдёт продуктивно!",
            "Молодец! Каждый день — новый шанс.",
            "Здорово, что ты пришёл! Шаг к знаниям никогда не бывает лишним.",
            "Верь в себя — именно сейчас ты строишь своё будущее.",
        ]
    return random.choice(phrases)


def get_student_by_device(request: Request, db: Session) -> Optional[Student]:
    device_uid = request.cookies.get("device_uid")
    if not device_uid:
        return None
    return (
        db.query(Student)
        .filter(Student.device_uid == device_uid, Student.is_active == True)
        .first()
    )


def get_current_admin(request: Request, db: Session) -> Optional[Admin]:
    token = request.cookies.get("admin_session")
    if not token:
        return None
    return db.query(Admin).filter(Admin.session_token == token).first()


# --------- СТУДЕНТЫ ---------
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    lang = get_lang(request)
    ensure_admin(db)

    # Студенты с ПК → страница "зайдите с телефона"
    if not is_mobile_request(request):
        return templates.TemplateResponse(
            "only_mobile.html",
            {"request": request, "lang": lang},
        )

    student = get_student_by_device(request, db)
    if student:
        return RedirectResponse(url="/student", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None, "lang": lang},
    )


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    lang = get_lang(request)
    login = login.strip()

    # ИЩЕМ ПО ПОЛЮ login И password ИЗ ТВОЕЙ БАЗЫ
    student = (
        db.query(Student)
        .filter(Student.login == login, Student.is_active == True)
        .first()
    )

    if not student or student.password != password:
        error_msg = (
            "Неверный логин или пароль"
            if lang == "ru"
            else "Қате логин немесе құпия сөз"
        )
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": error_msg, "lang": lang},
            status_code=400,
        )

    cookie_device_uid = request.cookies.get("device_uid")

    if student.device_uid is None:
        if not cookie_device_uid:
            cookie_device_uid = generate_device_uid()
        student.device_uid = cookie_device_uid
        db.commit()
    else:
        if not cookie_device_uid or cookie_device_uid != student.device_uid:
            error_msg = (
                "Это не привязанное устройство. Обратитесь к куратору."
                if lang == "ru"
                else "Бұл тіркелген құрылғы емес. Топ жетекшісіне жүгініңіз."
            )
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": error_msg, "lang": lang},
                status_code=403,
            )

    response = RedirectResponse(url="/student", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="device_uid",
        value=cookie_device_uid,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
    )
    return response


@app.get("/student", response_class=HTMLResponse)
def student_home(request: Request, db: Session = Depends(get_db)):
    lang = get_lang(request)

    if not is_mobile_request(request):
        return templates.TemplateResponse(
            "only_mobile.html",
            {"request": request, "lang": lang},
        )

    student = get_student_by_device(request, db)
    if not student:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    today = date.today()
    attendance_today = (
        db.query(Attendance)
        .filter(Attendance.student_id == student.id, Attendance.date == today)
        .first()
    )

    return templates.TemplateResponse(
        "student_home.html",
        {
            "request": request,
            "student": student,
            "today": today,
            "already_marked": attendance_today is not None,
            "motivation": attendance_today.motivation_text if attendance_today else None,
            "lang": lang,
            "error": None,
        },
    )


@app.post("/student/mark", response_class=HTMLResponse)
def mark_attendance(
    request: Request,
    lat: Optional[float] = Form(None),
    lon: Optional[float] = Form(None),
    db: Session = Depends(get_db),
):
    lang = get_lang(request)

    if not is_mobile_request(request):
        return templates.TemplateResponse(
            "only_mobile.html",
            {"request": request, "lang": lang},
        )

    student = get_student_by_device(request, db)
    if not student:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    today = date.today()
    attendance_today = (
        db.query(Attendance)
        .filter(Attendance.student_id == student.id, Attendance.date == today)
        .first()
    )

    if attendance_today:
        return RedirectResponse(url="/student", status_code=status.HTTP_302_FOUND)

    if lat is None or lon is None:
        error_msg = (
            "Не удалось получить геолокацию. Включите доступ к местоположению и попробуйте снова."
            if lang == "ru"
            else "Геолокация алынбады. Орналасқан жерге қолжеткізуді қосып, қайта көріңіз."
        )
        return templates.TemplateResponse(
            "student_home.html",
            {
                "request": request,
                "student": student,
                "today": today,
                "already_marked": False,
                "motivation": None,
                "lang": lang,
                "error": error_msg,
            },
            status_code=400,
        )

    distance = haversine_distance_m(lat, lon, COLLEGE_LAT, COLLEGE_LON)

    if distance > ALLOWED_RADIUS_METERS:
        error_msg = (
            "Вы находитесь вне территории колледжа. Отметиться можно только на территории учебного корпуса."
            if lang == "ru"
            else "Сіз колледж аумағынан тыссыз. Қатысуды тек оқу корпусы аумағында белгілеуге болады."
        )
        return templates.TemplateResponse(
            "student_home.html",
            {
                "request": request,
                "student": student,
                "today": today,
                "already_marked": False,
                "motivation": None,
                "lang": lang,
                "error": error_msg,
            },
            status_code=400,
        )

    motivation = generate_motivation_text(student, lang)
    record = Attendance(
        student_id=student.id,
        date=today,
        status=1,
        ip_address=request.client.host,
        device_uid=student.device_uid,
        motivation_text=motivation,
    )
    db.add(record)
    db.commit()

    return RedirectResponse(url="/student", status_code=status.HTTP_302_FOUND)


# --------- АДМИН ---------
@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_form(request: Request, db: Session = Depends(get_db)):
    lang = get_lang(request)
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "error": None, "lang": lang},
    )


@app.post("/admin/login", response_class=HTMLResponse)
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    lang = get_lang(request)
    admin = db.query(Admin).filter(Admin.username == username).first()

    if not admin or admin.password != password:
        error_msg = "Неверный логин или пароль"
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": error_msg, "lang": lang},
            status_code=400,
        )

    token = str(uuid.uuid4())
    admin.session_token = token
    db.commit()

    resp = RedirectResponse("/admin/dashboard", status_code=302)
    resp.set_cookie(
        "admin_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    return resp


@app.get("/admin/logout")
def admin_logout(request: Request, db: Session = Depends(get_db)):
    admin = get_current_admin(request, db)
    if admin:
        admin.session_token = None
        db.commit()
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie("admin_session")
    return resp


@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    lang = get_lang(request)
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    today = date.today()

    group_stats = (
        db.query(
            Student.group_name.label("group_name"),
            func.count(Student.id).label("total"),
            func.coalesce(
                func.sum(
                    case((Attendance.status == 1, 1), else_=0)
                ),
                0,
            ).label("present"),
        )
        .outerjoin(
            Attendance,
            (Attendance.student_id == Student.id) & (Attendance.date == today),
        )
        .group_by(Student.group_name)
        .order_by(Student.group_name)
        .all()
    )

    total_students = sum(g.total for g in group_stats)
    total_present = sum(g.present for g in group_stats)

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "lang": lang,
            "today": today,
            "group_stats": group_stats,
            "total_students": total_students,
            "total_present": total_present,
        },
    )
