from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from pydantic import EmailStr, constr
from passlib.context import CryptContext
from dotenv import load_dotenv
from database import SessionLocal, engine
from models import Base, Usuario
import aiohttp
import os
from pathlib import Path

# Cargar entorno desde llave.env
env_path = Path(__file__).resolve().parent / "llave.env"
load_dotenv(dotenv_path=env_path)

# Leer clave secreta reCAPTCHA
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

# Mostrar en consola a qué base de datos intenta conectarse
print("📦 Conectando a la base de datos con:", engine.url)

# Inicializar la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Dependencia para la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def mostrar_formulario(request: Request):
    return templates.TemplateResponse("main.html", {"request": request, "mensaje": ""})

@app.post("/registrar", response_class=HTMLResponse)
async def registrar_usuario(
    request: Request,
    nombre: str = Form(..., min_length=2, max_length=100),
    correo: EmailStr = Form(...),
    password: constr(min_length=6, max_length=100) = Form(...),
    g_recaptcha_response: str = Form(..., alias="g-recaptcha-response"),
    db: Session = Depends(get_db)
):
    # Verificar reCAPTCHA
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": RECAPTCHA_SECRET_KEY,
                "response": g_recaptcha_response
            }
        ) as resp:
            resultado = await resp.json()
            if not resultado.get("success"):
                return templates.TemplateResponse("main.html", {
                    "request": request,
                    "mensaje": "reCAPTCHA inválido"
                })

    # Verificar si ya existe el correo
    if db.query(Usuario).filter(Usuario.correo == correo).first():
        return templates.TemplateResponse("main.html", {
            "request": request,
            "mensaje": "El correo ya está registrado"
        })

    # Hashear contraseña
    hash_password = pwd_context.hash(password)

    nuevo_usuario = Usuario(
        nombre=nombre,
        correo=correo,
        password=hash_password
    )
    db.add(nuevo_usuario)
    db.commit()

    return templates.TemplateResponse("main.html", {
        "request": request,
        "mensaje": "Registro exitoso"
    })

# ⛑️ Manejo de errores de validación
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errores = []
    for error in exc.errors():
        campo = error.get("loc", [""])[-1]
        msg = error.get("msg", "")
        errores.append(f"{campo}: {msg}")
    return templates.TemplateResponse("main.html", {
        "request": request,
        "mensaje": " | ".join(errores)
    })
