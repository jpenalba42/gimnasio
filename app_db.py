from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Table
from werkzeug.security import generate_password_hash, check_password_hash

# from sqlalchemy.orm import joinedload

from dotenv import load_dotenv
import os

# Cargar variables del .env
load_dotenv()

# Obtener la variable de entorno
connection_string = os.getenv("DB_URL")
print("Conexión a la base de datos:", connection_string)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = connection_string
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Desactiva advertencias innecesarias
db = SQLAlchemy(app)

app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

Base = db.Model
Table = db.Table
Date = db.Date
Column = db.Column
Integer = db.Integer
String = db.String
Boolean = db.Boolean
relationship = db.relationship
ForeignKey = db.ForeignKey


usuario_habito = Table(
    'usuario_habito',
    Base.metadata,
    Column('usuario_id', Integer, ForeignKey('tabla_usuarios.id'), primary_key=True),
    Column('habito_id', Integer, ForeignKey('tabla_habitos.id'), primary_key=True)
)

class UsuarioDB(Base):
    __tablename__ = 'tabla_usuarios'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    rol = Column(String, nullable=False, default='usuario')
    
    habitos = relationship("HabitDB", secondary=usuario_habito, back_populates="usuarios")
    seguimientos = relationship("HabitTrackDB", back_populates="usuario")


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<UsuarioDB(id={self.id}, username={self.username})>"


class HabitDB(Base):
    __tablename__ = 'tabla_habitos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False)
    descripcion = Column(String, nullable=False)
    
    usuarios = relationship("UsuarioDB", secondary=usuario_habito, back_populates="habitos")
    seguimientos = relationship("HabitTrackDB", back_populates="habito")

    def __repr__(self):
        return f"<HabitDB(id={self.id}, nombre={self.nombre})>"


class HabitTrackDB(Base):
    __tablename__ = 'tabla_seguimiento'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('tabla_usuarios.id'), nullable=False)
    habit_id = Column(Integer, ForeignKey('tabla_habitos.id'), nullable=False)
    fecha = Column(Date, nullable=False)
    cumplido = Column(Boolean, nullable=False)

    usuario = relationship("UsuarioDB", back_populates="seguimientos")
    habito = relationship("HabitDB", back_populates="seguimientos")

""" with app.app_context():
    db.create_all()
 """

@app.before_request
def load_current_user():
    user_id = session.get('user_id')
    if user_id:
        g.current_user = UsuarioDB.query.get(user_id)
    else:
        g.current_user = None

@app.route('/')
def inicio():
    return render_template('base.html', current_user=g.current_user)


from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        user = UsuarioDB.query.get(user_id) if user_id else None
        if not user or user.rol != 'admin':
            flash('Acceso restringido a administradores.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    usuarios = UsuarioDB.query.all()
    habitos = HabitDB.query.all()
    seguimientos = HabitTrackDB.query.all()
    return render_template('admin_dashboard.html', usuarios=usuarios, habitos=habitos, seguimientos=seguimientos)


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if 'user_id' in session: # Si ya está logueado, redirigir al dashboard
        return redirect(url_for('listar_usuarios'))
    
    if request.method == "POST":
        username = request.form["usuario"]
        password = request.form["password"]
        confirm_password = request.form.get('confirm_password')

        if not username or not password or not confirm_password:
            flash('Todos los campos son obligatorios.', 'danger')
            return redirect(url_for('registro'))
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden.', 'danger')
            return redirect(url_for('registro'))
        
        existing_user = UsuarioDB.query.filter_by(username=username).first()
        if existing_user:
            flash('El nombre de usuario ya existe.', 'warning')
            return redirect(url_for('registro'))

        new_user = UsuarioDB(username=username)
        new_user.set_password(password) # Hashea la contraseña
        db.session.add(new_user)
        try:
            db.session.commit()
            flash('Cuenta creada exitosamente. Por favor, inicia sesión.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la cuenta: {str(e)}', 'danger')
            return redirect(url_for('registro'))
    
    return render_template('registro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: # Si ya está logueado, redirigir al dashboard
        return redirect(url_for('inicio'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
    
        if not username or not password:
            flash('Nombre de usuario y contraseña son obligatorios.', 'danger')
            return redirect(url_for('login'))
        
        user = UsuarioDB.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username # Guardar username para mostrarlo
            flash('Inicio de sesión exitoso!', 'success')
            return redirect(url_for('inicio'))
        else:
            flash('Nombre de usuario o contraseña incorrectos.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))


@app.route('/usuarios')
def listar_usuarios():
    usuarios = UsuarioDB.query.all()
    return render_template('usuarios.html', usuarios=usuarios)


""" @app.route("/nuevo_usuario", methods=["GET", "POST"])
def nuevo_usuario():
    if request.method == "POST":
        usuario = request.form["usuario"]
        nuevo_usuario = UsuarioDB(username=usuario)
        db.session.add(nuevo_usuario)
        db.session.commit()
        return redirect(url_for('listar_usuarios'))
    else:
        return render_template("nuevo_usuario.html") """

  
@app.route("/nuevo_habito", methods=["GET", "POST"])
def nuevo_habito():
    usuario_id = session.get('user_id')
    usuario = UsuarioDB.query.get(usuario_id)
    habitos_usuario = usuario.habitos  # hábitos asignados a este usuario
    if request.method == "POST":
        nombre = request.form["nombre"]
        descripcion = request.form["descripcion"]
        usuario_id = session.get('user_id')
        print("Usuario ID es", usuario_id)

        habito = HabitDB(nombre=nombre, descripcion=descripcion)
        usuario = UsuarioDB.query.get(usuario_id)
        habito.usuarios.append(usuario)
        db.session.add(habito)
        db.session.commit()

        return redirect(url_for('nuevo_habito'))
    return render_template("nuevo_habito.html", habitos_usuario=habitos_usuario, current_user=g.current_user)


@app.route("/registrar_seguimiento", methods=["GET", "POST"])
def nuevo_seguimiento():
    usuario_id = session.get('user_id')
    usuario = UsuarioDB.query.get(usuario_id)
    habitos = usuario.habitos  # hábitos asignados a este usuario
    seguimientos = usuario.seguimientos

    if request.method == "POST":
        habit_id = int(request.form["habit_id"])
        fecha = request.form["fecha"]
        cumplido = request.form.get("cumplido") == "on"  # Checkbox: 'on' si está marcado

        seguimiento = HabitTrackDB(
            user_id=usuario_id,
            habit_id=habit_id,
            fecha=fecha,
            cumplido=cumplido
        )
        db.session.add(seguimiento)
        db.session.commit()
        return redirect(url_for('nuevo_seguimiento'))
    
    return render_template("registrar_seguimiento.html", usuario=usuario, habitos=habitos, seguimientos=seguimientos, current_user=g.current_user)

""" @app.route("/registrar_seguimiento", methods=["GET", "POST"])
def registrar_seguimiento():
    usuarios = UsuarioDB.query.all()
    if request.method == "POST":
        usuario_id = int(request.form["usuario_id"])
        habito_id = int(request.form["habito_id"])
        fecha = request.form["fecha"]
        cumplido = bool(request.form.get("cumplido"))

        nuevo_seguimiento = HabitTrackDB(
            user_id=usuario_id,
            habit_id=habito_id,
            fecha=fecha,
            cumplido=cumplido
        )
        db.session.add(nuevo_seguimiento)
        db.session.commit()
        return redirect(url_for("listar_usuarios"))

    return render_template("registrar_seguimiento.html", usuarios=usuarios) """


if __name__ == '__main__':
    app.run(debug=True)