# main.py
from fastapi import FastAPI, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date
import uuid
import random
from math import radians, sin, cos, sqrt, atan2
from typing import Optional

from database import Base, engine, get_db
from models import Student, Attendance

app = FastAPI()

# Создаём таблицы в БД
Base.metadata.create_all(bind=engine)

# Статика и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ===== НАСТРОЙКИ ГЕОЗОНЫ (можно потом подправить) =====
# Примерно центр Талдыкоргана. Можно будет заменить на точные координаты колледжа.
COLLEGE_LAT = 45.01
COLLEGE_LON = 78.22
# Радиус в метрах, внутри которого разрешаем отметку
ALLOWED_RADIUS_METERS = 400  # 400 м вокруг точки


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками в метрах (формула хаверсинуса)."""
    R = 6371000  # радиус Земли в метрах
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


# ========== ЯЗЫК ==========

def get_lang(request: Request) -> str:
    """Читаем язык из cookie. По умолчанию RU."""
    lang = request.cookies.get("lang")
    if lang in ("ru", "kk"):
        return lang
    return "ru"


@app.get("/set-lang/{lang_code}")
def set_language(lang_code: str, request: Request):
    """Ставим cookie с языком и возвращаем пользователя назад."""
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


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def ensure_test_student(db: Session):
    """ВРЕМЕННО: создаём одного тестового студента, если БД пустая."""
    student = db.query(Student).first()
    if not student:
        s = Student(
            full_name="Иванов Иван",
            login="Иванов Иван",
            password="1234",
            group_name="IN-412",
        )
        db.add(s)
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


# ========== РОУТЫ ==========

@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    lang = get_lang(request)
    ensure_test_student(db)
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
    fio: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    lang = get_lang(request)
    fio = fio.strip()

    student = (
        db.query(Student)
        .filter(Student.login == fio, Student.is_active == True)
        .first()
    )

    if not student or student.password != password:
        error_msg = (
            "Неверное ФИО или пароль"
            if lang == "ru"
            else "Қате ТАӘ немесе құпия сөз"
        )
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": error_msg, "lang": lang},
            status_code=400,
        )

    cookie_device_uid = request.cookies.get("device_uid")

    if student.device_uid is None:
        # Первый вход – привязываем устройство
        if not cookie_device_uid:
            cookie_device_uid = generate_device_uid()
        student.device_uid = cookie_device_uid
        db.commit()
    else:
        # Уже есть привязка: проверяем устройство
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
    student = get_student_by_device(request, db)
    if not student:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    today = date.today()
    attendance_today = (
        db.query(Attendance)
        .filter(Attendance.student_id == student.id, Attendance.date == today)
        .first()
    )

    # Если уже отметился — просто уводим на страницу
    if attendance_today:
        return RedirectResponse(url="/student", status_code=status.HTTP_302_FOUND)

    # ==== Проверяем геолокацию ====
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

    # ==== Всё ок, отмечаем ====
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
