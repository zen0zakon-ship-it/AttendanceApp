# app/services.py
from datetime import datetime, date, timedelta
from math import radians, cos, sin, asin, sqrt

from sqlalchemy.orm import Session

from . import models


def haversine(lat1, lon1, lat2, lon2):
    # расстояние между точками в метрах
    R = 6371000  # Земля, радиус м
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c


def get_or_init_geo_settings(db: Session) -> models.GeoSettings:
    gs = db.query(models.GeoSettings).first()
    if not gs:
        # временно захардкодим центр, потом поправишь на координаты колледжа
        gs = models.GeoSettings(center_lat=45.0000, center_lon=78.0000, radius_m=300)
        db.add(gs)
        db.commit()
        db.refresh(gs)
    return gs


def build_message_for_student(db: Session, user: models.User, status: str) -> str:
    today = date.today()

    # последняя отметка до сегодня
    last = (
        db.query(models.Checkin)
        .filter(models.Checkin.user_id == user.id, models.Checkin.checkin_date < today)
        .order_by(models.Checkin.checkin_date.desc())
        .first()
    )

    days_absent = None
    if last:
        days_absent = (today - last.checkin_date).days

    # количество пропусков за 30 дней (очень грубо: дни без отметок)
    since = today - timedelta(days=30)
    checkins = (
        db.query(models.Checkin)
        .filter(models.Checkin.user_id == user.id,
                models.Checkin.checkin_date >= since)
        .all()
    )
    days_present = len({c.checkin_date for c in checkins})

    # считаем стрик (подряд до вчера)
    streak = 0
    d = today - timedelta(days=1)
    dates_present = {c.checkin_date for c in checkins}
    while d in dates_present:
        streak += 1
        d -= timedelta(days=1)

    # если подозрительно
    if status == "SUSPICIOUS":
        return "Система считает эту отметку подозрительной. Если это ошибка — подойди к куратору 👀"

    # если давно не было
    if days_absent is not None and days_absent >= 45:
        return f"Кавоооооо тебя не было {days_absent} дней, больше так не делай пожааалуйста! 😱"
    if days_absent is not None and days_absent >= 7:
        return f"Ты пропал на {days_absent} дней. Хорошо, что вернулся, так больше не пропадай 🥺"

    # если хорошая посещаемость
    if days_present >= 20 and status == "ON_TIME":
        return f"Красавчик! Уже {days_present} посещений за месяц, дисциплина на высоте 💪"
    if streak >= 5 and status == "ON_TIME":
        return f"Ты уже {streak} дней подряд без прогулов. Вот это настрой! 🔥"

    # если опоздал
    if status == "LATE":
        return "Сегодня ты немного опоздал(а). В следующий раз постарайся прийти вовремя 😉"

    # дефолт
    return "Отличная работа! Ты сегодня отметился, так держать! ✅"
