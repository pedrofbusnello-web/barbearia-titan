import sqlite3
import os
from werkzeug.security import generate_password_hash

if os.path.exists("barbearia.db"):
    os.remove("barbearia.db")
    print("✅ Banco antigo deletado")

conn = sqlite3.connect("barbearia.db")
c = conn.cursor()

print("Banco localizado em:")
print(os.path.abspath("barbearia.db"))

# =========================
# TABELA USUÁRIOS
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    telefone TEXT UNIQUE,
    senha TEXT NOT NULL,
    tipo TEXT DEFAULT 'cliente',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
print("✅ Tabela usuarios criada")

# =========================
# TABELA AGENDAMENTOS
# =========================
c.execute("""
    CREATE TABLE IF NOT EXISTS agendamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        nome TEXT,
        telefone TEXT,
        servico TEXT,
        plano TEXT,
        profissional TEXT,
        data TEXT,
        horario TEXT,
        pagamento TEXT,
        observacoes TEXT,
        status TEXT DEFAULT 'AGENDADO',
        tipo TEXT DEFAULT 'agendamento',
        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
print("✅ Tabela agendamentos criada")

# =========================
# TABELA ASSINATURAS VIP
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS assinaturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL,
    plano TEXT NOT NULL,
    profissional TEXT NOT NULL,
    pagamento TEXT NOT NULL,
    data_inicio TEXT NOT NULL,
    status TEXT DEFAULT 'ATIVA',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
print("✅ Tabela assinaturas criada")

# =========================
# BARBEIROS
# =========================
barbeiros = [
    ("joao",     "joao@barbearia.com",     "(54) 99999-9999", generate_password_hash("123456", method='pbkdf2:sha256'), "barbeiro"),
    ("pedro",    "pedro@barbearia.com",    "(54) 99999-9998", generate_password_hash("123456", method='pbkdf2:sha256'), "barbeiro"),
    ("bernardo", "bernardo@barbearia.com", "(54) 99999-9997", generate_password_hash("123456", method='pbkdf2:sha256'), "barbeiro"),
    ("pablo",    "pablo@barbearia.com",    "(54) 99999-9996", generate_password_hash("123456", method='pbkdf2:sha256'), "barbeiro"),
]
c.executemany("INSERT INTO usuarios (usuario, email, telefone, senha, tipo) VALUES (?, ?, ?, ?, ?)", barbeiros)
print("✅ Barbeiros inseridos")

# =========================
# CLIENTES DE TESTE
# =========================
clientes = [
    ("cliente1", "cliente1@email.com", "(54) 99999-0001", generate_password_hash("123456", method='pbkdf2:sha256'), "cliente"),
    ("cliente2", "cliente2@email.com", "(54) 99999-0002", generate_password_hash("123456", method='pbkdf2:sha256'), "cliente"),
]
c.executemany("INSERT INTO usuarios (usuario, email, telefone, senha, tipo) VALUES (?, ?, ?, ?, ?)", clientes)
print("✅ Clientes de teste inseridos")

conn.commit()
conn.close()

print("\n" + "="*60)
print("🎉 BANCO DE DADOS CRIADO COM SUCESSO!")
print("="*60)
print("\nBARBEIROS:  joao / pedro / bernardo / pablo  |  Senha: 123456")
print("CLIENTES:   cliente1 / cliente2               |  Senha: 123456")
print("="*60)