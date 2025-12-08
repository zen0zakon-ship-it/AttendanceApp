# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ВРЕМЕННАЯ база для теста (файл attendance.db в этой же папке)
# Потом сможешь заменить на SQL Server / PostgreSQL и т.д.
SQLALCHEMY_DATABASE_URL = "sqlite:///./attendance.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # нужно для SQLite + FastAPI
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- ВРЕМЕННЫЕ ДАННЫЕ ДЛЯ ТЕСТА ----------

def init_demo_data():
    """
    Создаём таблицы и добавляем:
    - админа (admin / admin123)
    - студента (demo / 1234)
    """
    from models import Student, Admin  # импорт здесь, чтобы не было круговой зависимости

    # создаём таблицы, если их ещё нет
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Админ по умолчанию
        admin = db.query(Admin).filter_by(username="admin").first()
        if not admin:
            admin = Admin(username="admin", password="admin123")
            db.add(admin)

        # Тестовый студент demo / 1234
        student = db.query(Student).filter_by(login="demo").first()
        if not student:
            student = Student(
                full_name="Тестовый Студент",
                login="demo",
                password="1234",
                group_name="SW-999",
                is_active=True,
            )
            db.add(student)

        db.commit()
    finally:
        db.close()


# вызывем инициализацию один раз при старте приложения
init_demo_data()
