from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import psycopg2
import psycopg2.extras
import os
import re
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'titan_secret_key_super_secreto_2026_MUDAR_EM_PRODUCAO')


# =========================
# HORÁRIO DE FUNCIONAMENTO
# =========================
HORARIO_FUNCIONAMENTO = {
    0: [("07:30", "11:30"), ("13:30", "20:00")],
    1: [("07:30", "11:30"), ("13:30", "20:00")],
    2: [("07:30", "11:30"), ("13:30", "20:00")],
    3: [("07:30", "11:30"), ("13:30", "20:00")],
    4: [("07:30", "11:30"), ("13:30", "20:00")],
    5: [("08:00", "11:30"), ("13:00", "18:00")],
    6: [],
}

INTERVALO_MINUTOS = 30


def gerar_horarios_disponiveis(data_str):
    try:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d")
    except ValueError:
        return []

    dia_semana = data_obj.weekday()
    periodos = HORARIO_FUNCIONAMENTO.get(dia_semana, [])

    horarios = []
    for inicio_str, fim_str in periodos:
        inicio = datetime.strptime(inicio_str, "%H:%M")
        fim    = datetime.strptime(fim_str,    "%H:%M")
        atual  = inicio
        while atual < fim:
            horarios.append(atual.strftime("%H:%M"))
            atual += timedelta(minutes=INTERVALO_MINUTOS)

    return horarios


# =========================
# VALIDAÇÕES
# =========================
def validar_telefone(telefone):
    """Aceita formatos brasileiros com 10 ou 11 dígitos."""
    numeros = re.sub(r'[^0-9]', '', telefone)
    return 10 <= len(numeros) <= 11


def validar_email_formato(email):
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(padrao, email))


# =========================
# AUXILIARES
# =========================
DATABASE_URL = os.environ.get("DATABASE_URL")

# Render às vezes fornece a URL como "postgres://", o SQLAlchemy exige
# "postgresql://" (o psycopg2 aceita as duas, mas já deixamos padronizado)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


def usuario_logado():
    return session.get("usuario")


def usuario_tipo():
    return session.get("tipo")


def verificar_login():
    return bool(usuario_logado())


def validar_data_horario(data, horario):
    try:
        data_obj = datetime.strptime(data, "%Y-%m-%d").date()
    except ValueError:
        return False, "⚠️ Data inválida!"

    if data_obj < datetime.now().date():
        return False, "⚠️ Não é possível agendar para uma data passada!"

    horarios_validos = gerar_horarios_disponiveis(data)

    if not horarios_validos:
        return False, "⚠️ A barbearia não funciona nesse dia!"

    if horario not in horarios_validos:
        return False, "⚠️ Horário inválido! Escolha um horário dentro do expediente, em intervalos de 30 minutos."

    if data_obj == datetime.now().date():
        agora = datetime.now().strftime("%H:%M")
        if horario <= agora:
            return False, "⚠️ Esse horário já passou!"

    return True, ""


def horario_disponivel(conn, profissional, data, horario, ignorar_id=None):
    c = conn.cursor()
    c.execute("""
        SELECT id FROM agendamentos
        WHERE profissional = %s AND data = %s AND horario = %s AND status != 'CANCELADO'
    """, (profissional, data, horario))

    row = c.fetchone()
    if row and ignorar_id and row["id"] == ignorar_id:
        return True
    return row is None


# =========================
# PÁGINA INICIAL
# =========================
@app.route("/")
def inicio():
    return render_template("inicio.html")


# =========================
# REDIRECT MINHA CONTA
# =========================
@app.route("/minhaconta-redirect")
def minhaconta_redirect():
    if usuario_logado():
        return redirect(url_for("minhaconta"))
    return redirect(url_for("login"))


# =========================
# INFORMAÇÕES
# =========================
@app.route("/informacoes")
def informacoes():
    return render_template("informacoes.html")


# =========================
# AGENDAMENTO ABERTO (SEM LOGIN)
# =========================
@app.route("/agendamento")
def agendamento():
    return render_template("agendamento.html")


@app.route("/agendar", methods=["POST"])
def agendar():
    try:
        usuario = session.get("usuario") or "visitante"

        servico      = request.form.get("servico",      "").strip()
        profissional = request.form.get("profissional", "").strip()
        data         = request.form.get("data",         "").strip()
        horario      = request.form.get("horario",      "").strip()
        pagamento    = request.form.get("pagamento",    "").strip()
        observacoes  = request.form.get("observacoes",  "").strip()
        nome         = request.form.get("nome",         "").strip()
        telefone     = request.form.get("telefone",     "").strip()

        if not all([servico, profissional, data, horario, pagamento, nome, telefone]):
            return render_template("agendamento.html", erro="⚠️ Preencha todos os campos obrigatórios!")

        if not validar_telefone(telefone):
            return render_template("agendamento.html", erro="⚠️ Telefone inválido! Use o formato (54) 99999-9999")

        valido, mensagem_erro = validar_data_horario(data, horario)
        if not valido:
            return render_template("agendamento.html", erro=mensagem_erro)

        conn = get_db_connection()

        if not horario_disponivel(conn, profissional, data, horario):
            conn.close()
            return render_template("agendamento.html", erro="⚠️ Horário já ocupado!")

        c = conn.cursor()
        c.execute("""
            INSERT INTO agendamentos
            (usuario, nome, telefone, servico, profissional, data, horario, pagamento, observacoes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (usuario, nome, telefone, servico, profissional,
              data, horario, pagamento, observacoes, "AGENDADO"))

        conn.commit()
        conn.close()

        return redirect(url_for("confirmacao"))

    except Exception as e:
        print(f"Erro ao agendar: {e}")
        return render_template("agendamento.html", erro="⚠️ Erro ao processar agendamento!")


@app.route("/confirmacao")
def confirmacao():
    return render_template("confirmacao.html")


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_input = request.form.get("usuario", "").strip()
        senha       = request.form.get("senha",   "").strip()

        if not login_input or not senha:
            return render_template("log.html", mensagem="❌ Preencha todos os campos", usuario_digitado=login_input)

        try:
            conn = get_db_connection()
            c    = conn.cursor()

            # Aceita login por usuário, email OU telefone
            c.execute("""
                SELECT id, usuario, tipo, senha FROM usuarios
                WHERE usuario = %s OR email = %s OR telefone = %s
            """, (login_input, login_input, login_input))

            user = c.fetchone()
            conn.close()

            if user and check_password_hash(user["senha"], senha):
                session["usuario"] = user["usuario"]  # sempre salva o username
                session["tipo"]    = user["tipo"]
                session.permanent  = True

                if session.get("plano_escolhido"):
                    plano = session.pop("plano_escolhido")
                    return redirect(url_for("planovip", plano=plano))

                return redirect(url_for("minhaconta"))
            else:
                return render_template("log.html", mensagem="❌ Usuário/email/telefone ou senha inválidos", usuario_digitado=login_input)

        except Exception as e:
            print(f"Erro ao fazer login: {e}")
            return render_template("log.html", mensagem="❌ Erro ao processar login", usuario_digitado=login_input)

    return render_template("log.html", mensagem="", usuario_digitado="")


# =========================
# RECUPERAR SENHA
# =========================
@app.route("/recuperar-senha", methods=["GET", "POST"])
def recuperar_senha():
    if request.method == "POST":
        email = request.form.get("email", "").strip()

        if not email:
            return render_template("recuperar_senha.html", mensagem="❌ Digite seu email", enviado=False)

        if not validar_email_formato(email):
            return render_template("recuperar_senha.html", mensagem="❌ Email inválido", enviado=False)

        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT usuario FROM usuarios WHERE email = %s", (email,))
            user = c.fetchone()
            conn.close()

            if not user:
                return render_template("recuperar_senha.html", mensagem="❌ Email não encontrado", enviado=False)

            return render_template("recuperar_senha.html", mensagem="✅ Verifique seu email!", enviado=True)

        except Exception as e:
            print(f"Erro ao recuperar senha: {e}")
            return render_template("recuperar_senha.html", mensagem="❌ Erro ao processar", enviado=False)

    return render_template("recuperar_senha.html", mensagem="", enviado=False)


# =========================
# CADASTRO
# =========================
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        usuario   = request.form.get("usuario",   "").strip()
        email     = request.form.get("email",     "").strip()
        telefone  = request.form.get("telefone",  "").strip()
        senha     = request.form.get("senha",     "").strip()
        confsenha = request.form.get("confsenha", "").strip()

        if not all([usuario, email, telefone, senha, confsenha]):
            return render_template("cadastro.html", mensagem="❌ Preencha todos os campos")

        if len(usuario) < 3:
            return render_template("cadastro.html", mensagem="❌ Usuário deve ter no mínimo 3 caracteres")

        if not validar_email_formato(email):
            return render_template("cadastro.html", mensagem="❌ Email inválido")

        if not validar_telefone(telefone):
            return render_template("cadastro.html", mensagem="❌ Telefone inválido! Use o formato (54) 99999-9999")

        if len(senha) < 6:
            return render_template("cadastro.html", mensagem="❌ Senha deve ter no mínimo 6 caracteres")

        if senha != confsenha:
            return render_template("cadastro.html", mensagem="❌ Senhas não coincidem")

        try:
            conn = get_db_connection()
            c    = conn.cursor()

            senha_hash = generate_password_hash(senha, method='pbkdf2:sha256')

            c.execute("""
                INSERT INTO usuarios (usuario, email, telefone, senha, tipo)
                VALUES (%s, %s, %s, %s, %s)
            """, (usuario, email, telefone, senha_hash, "cliente"))

            conn.commit()
            conn.close()

            session["usuario"] = usuario
            session["tipo"]    = "cliente"
            session.permanent  = True

            if session.get("plano_escolhido"):
                plano = session.pop("plano_escolhido")
                return redirect(url_for("planovip", plano=plano))

            return redirect(url_for("minhaconta"))

        except psycopg2.IntegrityError:
            conn.rollback()
            conn.close()
            return render_template("cadastro.html", mensagem="❌ Usuário, email ou telefone já cadastrado")
        except Exception as e:
            print(f"Erro ao cadastrar: {e}")
            return render_template("cadastro.html", mensagem="❌ Erro ao processar cadastro")

    return render_template("cadastro.html", mensagem="")


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("inicio"))


# =========================
# CLUBE VIP
# =========================
@app.route("/vip")
def vip():
    return render_template("clube.html")


@app.route("/escolher-plano/<plano>")
def escolher_plano(plano):
    planos_validos = [
        "corte-basico-cabelo", "corte-basico-barba",
        "corte-premium-cabelo", "corte-premium-barba",
        "cabelo-barba-basico", "cabelo-barba-premium",
    ]

    if plano not in planos_validos:
        return redirect(url_for("vip"))

    if not usuario_logado():
        session["plano_escolhido"] = plano
        return redirect(url_for("login"))

    return redirect(url_for("planovip", plano=plano))


@app.route("/planovip/<plano>")
def planovip(plano):
    if not verificar_login():
        return redirect(url_for("login"))

    planos = {
        "corte-basico-cabelo":  {"nome": "Corte básico de cabelo",  "valor": 70},
        "corte-basico-barba":   {"nome": "Corte básico de barba",   "valor": 40},
        "corte-premium-cabelo": {"nome": "Corte premium de cabelo", "valor": 130},
        "corte-premium-barba":  {"nome": "Corte premium de barba",  "valor": 70},
        "cabelo-barba-basico":  {"nome": "Cabelo + Barba básico",   "valor": 130},
        "cabelo-barba-premium": {"nome": "Cabelo + Barba premium",  "valor": 190},
    }

    if plano not in planos:
        return redirect(url_for("vip"))

    session["plano_atual"]  = plano
    session["plano_nome"]   = planos[plano]["nome"]
    session["plano_valor"]  = planos[plano]["valor"]

    return render_template("planovip.html", plano=planos[plano]["nome"], valor=planos[plano]["valor"])


# =========================
# CHECKOUT DO PLANO
# =========================
@app.route("/coud", methods=["POST"])
def coud():
    if not verificar_login():
        return redirect(url_for("login"))

    plano        = session.get("plano_nome",  "")
    valor        = session.get("plano_valor", 0)
    profissional = request.form.get("profissional", "").strip()
    pagamento    = request.form.get("pagamento",    "").strip()

    if not profissional or not pagamento:
        return redirect(url_for("planovip", plano=session.get("plano_atual", "")))

    session["plano_checkout"]       = plano
    session["profissional_checkout"] = profissional
    session["pagamento_checkout"]    = pagamento

    if pagamento == "Pix":
        return redirect(url_for("pix", valor=valor, plano=plano, profissional=profissional))

    return render_template("coud.html", plano=plano, profissional=profissional, pagamento=pagamento)


# =========================
# PIX
# =========================
@app.route("/pix")
def pix():
    if not verificar_login():
        return redirect(url_for("login"))

    valor        = request.args.get("valor",        session.get("plano_valor", 0))
    plano        = request.args.get("plano",        session.get("plano_nome",  ""))
    profissional = request.args.get("profissional", session.get("profissional_checkout", ""))

    return render_template("pix.html", valor=valor, plano=plano, profissional=profissional)


@app.route("/pix_confirmado", methods=["POST"])
def pix_confirmado():
    if not verificar_login():
        return redirect(url_for("login"))

    plano        = request.form.get("plano",        "").strip()
    profissional = request.form.get("profissional", "").strip()

    session["plano_checkout"]        = plano
    session["profissional_checkout"] = profissional
    session["pagamento_checkout"]    = "Pix"

    return render_template("coud.html", plano=plano, profissional=profissional, pagamento="Pix")


# =========================
# CONFIRMAÇÃO DE AGENDAMENTO (PLANO VIP)
# =========================
@app.route("/confagen", methods=["GET", "POST"])
def confagen():
    if not verificar_login():
        return redirect(url_for("login"))

    if request.method == "POST":
        usuario      = usuario_logado()
        plano        = session.get("plano_checkout",        "")
        profissional = session.get("profissional_checkout", "")
        pagamento    = session.get("pagamento_checkout",    "")
        data         = request.form.get("data",    "").strip()
        horario      = request.form.get("horario", "").strip()

        if not all([plano, profissional, data, horario, pagamento]):
            return render_template("confagen.html", erro="⚠️ Preencha todos os campos!", plano=plano, profissional=profissional)

        valido, mensagem_erro = validar_data_horario(data, horario)
        if not valido:
            return render_template("confagen.html", erro=mensagem_erro, plano=plano, profissional=profissional)

        try:
            conn = get_db_connection()

            if not horario_disponivel(conn, profissional, data, horario):
                conn.close()
                return render_template("confagen.html", erro="⚠️ Horário já ocupado!", plano=plano, profissional=profissional)

            c = conn.cursor()

            # Salva agendamento
            c.execute("""
                INSERT INTO agendamentos
                (usuario, plano, profissional, data, horario, pagamento, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (usuario, plano, profissional, data, horario, pagamento, "AGENDADO"))

            # Salva assinatura VIP
            c.execute("""
                INSERT INTO assinaturas (usuario, plano, profissional, pagamento, data_inicio, status)
                VALUES (%s, %s, %s, %s, %s, 'ATIVA')
            """, (usuario, plano, profissional, pagamento, datetime.now().strftime("%Y-%m-%d")))

            conn.commit()
            conn.close()

            # Guarda dados para a tela de confirmação
            session["conf_vip_plano"]        = plano
            session["conf_vip_profissional"] = profissional
            session["conf_vip_data"]         = data
            session["conf_vip_horario"]      = horario
            session["conf_vip_pagamento"]    = pagamento

            # Limpa sessão de checkout
            for key in ["plano_checkout", "profissional_checkout", "pagamento_checkout", "plano_atual"]:
                session.pop(key, None)

            return redirect(url_for("confirmacao_vip"))

        except Exception as e:
            print(f"Erro ao confirmar agendamento VIP: {e}")
            return render_template("confagen.html", erro="⚠️ Erro ao processar agendamento!", plano=plano, profissional=profissional)

    plano        = session.get("plano_checkout",        "")
    profissional = session.get("profissional_checkout", "")

    return render_template("confagen.html", plano=plano, profissional=profissional, erro="")


# =========================
# CONFIRMAÇÃO VIP
# =========================
@app.route("/confirmacao-vip")
def confirmacao_vip():
    if not verificar_login():
        return redirect(url_for("login"))

    plano        = session.pop("conf_vip_plano",        "")
    profissional = session.pop("conf_vip_profissional", "")
    data         = session.pop("conf_vip_data",         "")
    horario      = session.pop("conf_vip_horario",      "")
    pagamento    = session.pop("conf_vip_pagamento",    "")

    return render_template("confirmacao_vip.html",
        plano=plano, profissional=profissional,
        data=data, horario=horario, pagamento=pagamento)


# =========================
# MINHA CONTA (UNIFICADA)
# =========================
@app.route("/minhaconta")
def minhaconta():
    usuario = usuario_logado()
    tipo    = usuario_tipo()

    if not usuario:
        return redirect(url_for("login"))

    try:
        conn = get_db_connection()
        c    = conn.cursor()

        if tipo == "barbeiro":
            c.execute("""
                SELECT id,
                       COALESCE(nome, usuario)    AS nome,
                       COALESCE(servico, plano)   AS servico,
                       data, horario, status,
                       COALESCE(telefone, '-')    AS telefone,
                       COALESCE(observacoes, '-') AS observacoes,
                       COALESCE(pagamento, '-')   AS pagamento
                FROM agendamentos
                WHERE profissional = %s
                ORDER BY data ASC, horario ASC
            """, (usuario,))

            agenda   = c.fetchall() or []
            pendentes = sum(1 for a in agenda if a["status"] == "AGENDADO")
            conn.close()

            return render_template("minhacb.html", agenda=agenda, pendentes=pendentes)

        else:
            hoje = datetime.now().strftime("%Y-%m-%d")

            c.execute("""
                SELECT servico, plano, data, horario, profissional
                FROM agendamentos
                WHERE usuario = %s AND data >= %s AND status != 'CANCELADO'
                ORDER BY data ASC, horario ASC
                LIMIT 1
            """, (usuario, hoje))
            proximo = c.fetchone()

            c.execute("""
                SELECT id, servico, plano, data, horario, profissional, status
                FROM agendamentos
                WHERE usuario = %s
                ORDER BY data DESC
                LIMIT 10
            """, (usuario,))
            agendamentos = c.fetchall() or []
            conn.close()

            return render_template("minhacc.html",
                agendamentos=agendamentos,
                proximo=proximo,
                hoje=hoje)

    except Exception as e:
        print(f"Erro ao carregar minha conta: {e}")
        return redirect(url_for("inicio"))


# =========================
# CANCELAR MEU AGENDAMENTO (CLIENTE)
# =========================
@app.route("/cancelar-meu-agendamento/<int:id>")
def cancelar_meu_agendamento(id):
    usuario = usuario_logado()
    if not usuario:
        return redirect(url_for("login"))

    try:
        conn = get_db_connection()
        c    = conn.cursor()

        c.execute("""
            SELECT id, data, horario, status FROM agendamentos
            WHERE id = %s AND usuario = %s
        """, (id, usuario))
        ag = c.fetchone()

        if not ag or ag["status"] == "CANCELADO":
            conn.close()
            return redirect(url_for("minhaconta"))

        # Verifica se faltam pelo menos 2 horas
        try:
            data_hora_ag = datetime.strptime(f"{ag['data']} {ag['horario']}", "%Y-%m-%d %H:%M")
            if (data_hora_ag - datetime.now()).total_seconds() < 7200:
                conn.close()
                return redirect(url_for("minhaconta"))
        except Exception:
            pass

        c.execute("""
            UPDATE agendamentos SET status = 'CANCELADO'
            WHERE id = %s AND usuario = %s
        """, (id, usuario))

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Erro ao cancelar agendamento: {e}")

    return redirect(url_for("minhaconta"))


# =========================
# MEUS DADOS
# =========================
@app.route("/meusdados")
def meusdados():
    usuario = usuario_logado()
    if not usuario:
        return redirect(url_for("login"))

    try:
        conn = get_db_connection()
        c    = conn.cursor()
        c.execute("SELECT usuario, email, telefone FROM usuarios WHERE usuario = %s", (usuario,))
        user = c.fetchone()
        conn.close()
        return render_template("meusdados.html", user=user)

    except Exception as e:
        print(f"Erro ao carregar dados: {e}")
        return redirect(url_for("minhaconta"))


# =========================
# EDITAR DADOS
# =========================
@app.route("/editar-dados", methods=["GET", "POST"])
def editar_dados():
    usuario = usuario_logado()
    if not usuario:
        return redirect(url_for("login"))

    conn = get_db_connection()
    c    = conn.cursor()
    c.execute("SELECT usuario, email, telefone, senha FROM usuarios WHERE usuario = %s", (usuario,))
    user = c.fetchone()

    if request.method == "POST":
        email           = request.form.get("email",           "").strip()
        telefone        = request.form.get("telefone",        "").strip()
        senha_atual     = request.form.get("senha_atual",     "").strip()
        nova_senha      = request.form.get("nova_senha",      "").strip()
        conf_nova_senha = request.form.get("conf_nova_senha", "").strip()

        if not validar_email_formato(email):
            conn.close()
            return render_template("editar_dados.html", user=user, mensagem="❌ Email inválido")

        if not validar_telefone(telefone):
            conn.close()
            return render_template("editar_dados.html", user=user, mensagem="❌ Telefone inválido! Use o formato (54) 99999-9999")

        # Troca de senha (opcional)
        nova_senha_hash = None
        if nova_senha:
            if not senha_atual or not check_password_hash(user["senha"], senha_atual):
                conn.close()
                return render_template("editar_dados.html", user=user, mensagem="❌ Senha atual incorreta")
            if nova_senha != conf_nova_senha:
                conn.close()
                return render_template("editar_dados.html", user=user, mensagem="❌ As novas senhas não coincidem")
            if len(nova_senha) < 6:
                conn.close()
                return render_template("editar_dados.html", user=user, mensagem="❌ Nova senha deve ter no mínimo 6 caracteres")
            nova_senha_hash = generate_password_hash(nova_senha, method='pbkdf2:sha256')

        try:
            if nova_senha_hash:
                c.execute("""
                    UPDATE usuarios SET email = %s, telefone = %s, senha = %s
                    WHERE usuario = %s
                """, (email, telefone, nova_senha_hash, usuario))
            else:
                c.execute("""
                    UPDATE usuarios SET email = %s, telefone = %s
                    WHERE usuario = %s
                """, (email, telefone, usuario))

            conn.commit()
            conn.close()
            return redirect(url_for("meusdados"))

        except psycopg2.IntegrityError:
            conn.rollback()
            conn.close()
            return render_template("editar_dados.html", user=user, mensagem="❌ Email ou telefone já está em uso por outra conta")
        except Exception as e:
            print(f"Erro ao editar dados: {e}")
            conn.close()
            return render_template("editar_dados.html", user=user, mensagem="❌ Erro ao salvar alterações")

    conn.close()
    return render_template("editar_dados.html", user=user, mensagem="")


# =========================
# BLOQUEAR HORÁRIO (BARBEIRO)
# =========================
@app.route("/bloquear-horario", methods=["GET", "POST"])
def bloquear_horario():
    usuario = usuario_logado()
    tipo    = usuario_tipo()

    if not usuario or tipo != "barbeiro":
        return redirect(url_for("login"))

    if request.method == "POST":
        data    = request.form.get("data",    "").strip()
        horario = request.form.get("horario", "").strip()

        if not data or not horario:
            return render_template("bloquear_horario.html", erro="⚠️ Preencha todos os campos!")

        valido, mensagem_erro = validar_data_horario(data, horario)
        if not valido:
            return render_template("bloquear_horario.html", erro=mensagem_erro)

        try:
            conn = get_db_connection()

            if not horario_disponivel(conn, usuario, data, horario):
                conn.close()
                return render_template("bloquear_horario.html", erro="⚠️ Horário já ocupado ou bloqueado!")

            c = conn.cursor()
            c.execute("""
                INSERT INTO agendamentos
                (usuario, nome, profissional, data, horario, status, tipo)
                VALUES (%s, 'BLOQUEIO', %s, %s, %s, 'BLOQUEADO', 'bloqueio')
                """, (usuario, usuario, data, horario))

            conn.commit()
            conn.close()

            return render_template("bloquear_horario.html", mensagem="✅ Horário bloqueado com sucesso!")

        except Exception as e:
            print(f"Erro ao bloquear horário: {e}")
            return render_template("bloquear_horario.html", erro="⚠️ Erro ao bloquear horário!")

    return render_template("bloquear_horario.html", erro="", mensagem="")


# =========================
# ATUALIZAR STATUS (BARBEIRO)
# =========================
@app.route("/atualizar-status/<int:id>/<status>")
def atualizar_status(id, status):
    usuario = usuario_logado()
    tipo    = usuario_tipo()

    if not usuario or tipo != "barbeiro":
        return redirect(url_for("login"))

    status_validos = ["CONFIRMADO", "CONCLUIDO", "CANCELADO"]
    if status not in status_validos:
        return redirect(url_for("minhaconta"))

    try:
        conn = get_db_connection()
        c    = conn.cursor()
        c.execute("""
            UPDATE agendamentos SET status = %s
            WHERE id = %s AND profissional = %s
        """, (status, id, usuario))
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Erro ao atualizar status: {e}")

    return redirect(url_for("minhaconta"))


# =========================
# API: HORÁRIOS DISPONÍVEIS
# =========================
@app.route("/horarios-disponiveis")
def horarios_disponiveis_api():
    data         = request.args.get("data",         "").strip()
    profissional = request.args.get("profissional", "").strip()

    todos_horarios = gerar_horarios_disponiveis(data)

    if not todos_horarios:
        return jsonify({"horarios": []})

    if profissional:
        try:
            conn = get_db_connection()
            c    = conn.cursor()
            c.execute("""
                SELECT horario FROM agendamentos
                WHERE profissional = %s AND data = %s AND status != 'CANCELADO'
            """, (profissional, data))
            ocupados = {row["horario"] for row in c.fetchall()}
            conn.close()
            todos_horarios = [h for h in todos_horarios if h not in ocupados]
        except Exception as e:
            print(f"Erro ao buscar horários ocupados: {e}")

    try:
        data_obj = datetime.strptime(data, "%Y-%m-%d").date()
        if data_obj == datetime.now().date():
            agora = datetime.now().strftime("%H:%M")
            todos_horarios = [h for h in todos_horarios if h > agora]
    except ValueError:
        pass

    return jsonify({"horarios": todos_horarios})


# =========================
# INICIALIZA BANCO (PostgreSQL/Render)
# =========================
def init_db():
    conn = get_db_connection()
    c    = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            usuario TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            telefone TEXT UNIQUE,
            senha TEXT NOT NULL,
            tipo TEXT DEFAULT 'cliente',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS agendamentos (
            id SERIAL PRIMARY KEY,
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
            tipo TEXT,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS assinaturas (
            id SERIAL PRIMARY KEY,
            usuario TEXT NOT NULL,
            plano TEXT NOT NULL,
            profissional TEXT NOT NULL,
            pagamento TEXT NOT NULL,
            data_inicio TEXT NOT NULL,
            status TEXT DEFAULT 'ATIVA',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# Cria as tabelas automaticamente ao subir o app no Render
# (roda 1x quando o worker inicia; se a tabela já existir, o CREATE TABLE
# IF NOT EXISTS simplesmente não faz nada)
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"Erro ao inicializar banco: {e}")


@app.before_request
def configurar_sessao():
    app.permanent_session_lifetime = 3600


@app.errorhandler(404)
def nao_encontrado(e):
    return redirect(url_for("inicio")), 404


@app.errorhandler(500)
def erro_servidor(e):
    print(f"Erro 500: {e}")
    return redirect(url_for("inicio")), 500


if __name__ == "__main__":
    app.run(debug=False)
    # Troque debug=True durante desenvolvimento local