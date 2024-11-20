from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask_migrate import Migrate


# Configuración de la aplicación
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')  # Clave de seguridad
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'  # Base de datos SQLite
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'  # Categoría para mensajes flash de inicio de sesión


# Modelos de base de datos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)  # Contraseña cifrada
    modules_completed = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Module(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    week = db.Column(db.Integer, nullable=False)
    exercises = db.relationship('Exercise', backref='module', lazy=True)

class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=False)

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=False)
    module = db.relationship('Module', backref=db.backref('lessons', lazy=True))


class ExerciseAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    answer = db.Column(db.Text, nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relación con el modelo Exercise y User
    exercise = db.relationship('Exercise', backref=db.backref('answers', lazy=True))
    user = db.relationship('User', backref=db.backref('answers', lazy=True))


# Formularios
class RegistrationForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired()])
    email = StringField('Correo Electrónico', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Registrarse')

class LoginForm(FlaskForm):
    email = StringField('Correo Electrónico', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')

# Función de carga de usuario para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Rutas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Verificar si el correo o el nombre de usuario ya existen
        if User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first():
            flash('Nombre de usuario o correo ya en uso.', 'danger')
            return redirect(url_for('register'))

        # Crear nuevo usuario con contraseña cifrada
        new_user = User(username=form.username.data, email=form.email.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash('Registro exitoso. Bienvenido!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Autenticación de usuario
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Correo o contraseña incorrectos.', 'danger')
    return render_template('login.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    modules = Module.query.all()  # Obtener todos los módulos
    return render_template('dashboard.html', user=current_user, modules=modules)

def get_lessons_by_module_id(module_id):
    return Lesson.query.filter_by(module_id=module_id).all()

# Función para obtener un módulo por su ID
def get_module_by_id(module_id):
    return Module.query.get_or_404(module_id)

@app.route('/module/<int:module_id>')
def module(module_id):
    module = get_module_by_id(module_id)
    lessons = get_lessons_by_module_id(module_id)

    # Filtrar las lecciones que son None o que no tienen atributo 'id'
    lessons = [lesson for lesson in lessons if lesson and lesson.id is not None]

    return render_template('module.html', module=module, lessons=lessons)


@app.route('/forum')
@login_required
def forum():
    return render_template('forum.html')

@app.route('/certificate')
@login_required
def certificate():
    return render_template('certificate.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

@app.route('/start_course')
def start_course():
    # Obtén todos los módulos (clases) desde la base de datos
    modules = Module.query.all()

    # Para cada módulo, obtén sus ejercicios relacionados
    module_exercises = {}
    for module in modules:
        exercises = Exercise.query.filter_by(module_id=module.id).all()
        module_exercises[module.id] = exercises

    return render_template('start_course.html', modules=modules, module_exercises=module_exercises)

@app.route('/lesson/<int:lesson_id>')
@login_required
def view_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    return render_template('lesson.html', lesson=lesson)

@app.route('/exercise/<int:exercise_id>')
@login_required
def exercise_detail(exercise_id):
    exercise = Exercise.query.get_or_404(exercise_id)
    # Redirigir al editor con el ID del ejercicio
    return redirect(url_for('editor', exercise_id=exercise.id))

@app.route('/editor/<int:exercise_id>', methods=['GET', 'POST'])
@login_required
def editor(exercise_id):
    # Obtener el ejercicio con el id correspondiente
    exercise = Exercise.query.get_or_404(exercise_id)

    # Obtener las respuestas posibles para este ejercicio
    answers = ExerciseAnswer.query.filter_by(exercise_id=exercise_id).all()

    # Si el formulario es enviado (POST)
    if request.method == 'POST':
        # Obtener la descripción actualizada del ejercicio
        new_description = request.form['description']
        exercise.description = new_description

        # Aquí puedes manejar la validación del código enviado por el usuario (opcional)
        code_submitted = request.form['code']  # El código enviado por el usuario
        is_correct = False

        # Validación del código enviado, esto depende de la lógica de tu aplicación
        # Por ejemplo, si el código debe devolver cierto resultado, lo validas aquí
        # Para esta demo, se podría validar si el código enviado es correcto
        if code_submitted == "respuesta correcta":  # Aquí deberías poner la lógica para validar el código
            is_correct = True

        # Si quieres guardar las respuestas del usuario, también puedes hacerlo aquí
        user_answer = request.form['user_answer']
        answer = ExerciseAnswer.query.get_or_404(user_answer)  # Se puede asociar la respuesta al ejercicio
        answer.user_id = current_user.id  # Asocia la respuesta con el usuario actual

        # Si el código es correcto, guardamos la respuesta como correcta
        if is_correct:
            answer.correct = True
        else:
            answer.correct = False

        # Guardar todos los cambios en la base de datos
        db.session.commit()

        # Redirigir al usuario de vuelta al módulo donde estaba el ejercicio
        return redirect(url_for('view_module', module_id=exercise.module_id))

    # Si es una solicitud GET, mostramos el formulario con los datos actuales del ejercicio
    return render_template('editor.html', exercise=exercise, answers=answers)

@app.route('/contacto')
@login_required
def contacto():
    return render_template('contacto.html')

# Ejecutar la aplicación
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
