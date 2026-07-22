import os
import psycopg2
from werkzeug.security import generate_password_hash

DATABASE_URL = os.environ["DATABASE_URL"]

conn = psycopg2.connect(DATABASE_URL)
c = conn.cursor()

# =========================
# TABELA USUARIOS
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    usuario VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(150) UNIQUE,
    telefone VARCHAR(30) UNIQUE,
    senha TEXT NOT NULL,
    tipo VARCHAR(20) DEFAULT 'cliente',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================
# TABELA AGENDAMENTOS
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS agendamentos (
    id SERIAL PRIMARY KEY,
    usuario VARCHAR(100),
    nome VARCHAR(100),
    telefone VARCHAR(30),
    servico VARCHAR(100),
    plano VARCHAR(100),
    profissional VARCHAR(100),
    data VARCHAR(20),
    horario VARCHAR(20),
    pagamento VARCHAR(50),
    observacoes TEXT,
    status VARCHAR(30) DEFAULT 'AGENDADO',
    tipo VARCHAR(30) DEFAULT 'agendamento',
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================
# TABELA ASSINATURAS
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS assinaturas (
    id SERIAL PRIMARY KEY,
    usuario VARCHAR(100),
    plano VARCHAR(100),
    profissional VARCHAR(100),
    pagamento VARCHAR(100),
    data_inicio VARCHAR(30),
    status VARCHAR(30) DEFAULT 'ATIVA',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================
# BARBEIROS
# =========================

barbeiros = [
    ("joao","joao@barbearia.com","(54)99999-9999",generate_password_hash("123456"),"barbeiro"),
    ("pedro","pedro@barbearia.com","(54)99999-9998",generate_password_hash("123456"),"barbeiro"),
    ("bernardo","bernardo@barbearia.com","(54)99999-9997",generate_password_hash("123456"),"barbeiro"),
    ("pablo","pablo@barbearia.com","(54)99999-9996",generate_password_hash("123456"),"barbeiro")
]

for b in barbeiros:
    c.execute("""
        INSERT INTO usuarios(usuario,email,telefone,senha,tipo)
        VALUES(%s,%s,%s,%s,%s)
        ON CONFLICT(usuario) DO NOTHING
    """, b)

conn.commit()
conn.close()

print("Banco PostgreSQL criado com sucesso!")