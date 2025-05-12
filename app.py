from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify # Убедитесь, что jsonify импортирован
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# ВАЖНО: Убедитесь, что secret_key установлен и уникален!
app.secret_key = "your_very_secret_strong_key_please_change_it_again_and_again_and_again" 
DATABASE = 'database.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # ... (код init_db остается без изменений) ...
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
        
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE name = ?", ('admin',))
        admin_exists = cursor.fetchone()
        if not admin_exists:
            hashed_password = generate_password_hash('admin123') # СМЕНИТЕ ЭТОТ ПАРОЛЬ
            cursor.execute("INSERT INTO users (name, password) VALUES (?, ?)", ('admin', hashed_password))
            db.commit()
        db.close()


# --- Функции для работы с расходами (остаются без изменений) ---
def get_all_expenses():
    db = get_db()
    expenses = db.execute(
        'SELECT e.id, e.date, e.amount, e.category_id, c.name as category_name '
        'FROM expenses e LEFT JOIN categories c ON e.category_id = c.id '
        'ORDER BY e.date DESC, e.id DESC'
    ).fetchall()
    db.close()
    return expenses

def add_expense(date, amount, category_id):
    db = get_db()
    db.execute('INSERT INTO expenses (date, amount, category_id) VALUES (?, ?, ?)', 
               (date, amount, category_id if category_id else None))
    db.commit()
    db.close()

# get_expense_by_id не используется текущим модальным окном редактирования трат, но может быть полезен
def get_expense_by_id(expense_id):
    db = get_db()
    expense = db.execute('SELECT id, date, amount, category_id FROM expenses WHERE id = ?', (expense_id,)).fetchone()
    db.close()
    return expense

def update_expense(expense_id, date, amount, category_id):
    db = get_db()
    db.execute('UPDATE expenses SET date = ?, amount = ?, category_id = ? WHERE id = ?', 
               (date, amount, category_id if category_id else None, expense_id))
    db.commit()
    db.close()

# --- Функции для работы с категориями ---
def get_all_categories_from_db():
    db = get_db()
    categories = db.execute('SELECT id, name FROM categories ORDER BY name').fetchall()
    db.close()
    return categories

def add_category_to_db(name):
    db = get_db()
    try:
        db.execute('INSERT INTO categories (name) VALUES (?)', (name,))
        db.commit()
        return True, "Категория успешно добавлена." # Возвращаем сообщение
    except sqlite3.IntegrityError: # Предполагаем UNIQUE constraint
        return False, f"Категория '{name}' уже существует."
    finally:
        db.close()

def get_category_by_id_from_db(category_id): # Новая функция
    db = get_db()
    category = db.execute('SELECT id, name FROM categories WHERE id = ?', (category_id,)).fetchone()
    db.close()
    return category

def update_category_in_db(category_id, new_name): # Новая функция
    db = get_db()
    try:
        # Проверяем, существует ли ДРУГАЯ категория с таким же новым именем (без учета регистра)
        existing_category_with_new_name = db.execute(
            'SELECT id FROM categories WHERE lower(name) = lower(?) AND id != ?',
            (new_name, category_id)
        ).fetchone()
        
        if existing_category_with_new_name:
            return False, f"Категория с названием '{new_name}' уже существует."

        db.execute('UPDATE categories SET name = ? WHERE id = ?', (new_name, category_id))
        db.commit()
        return True, "Категория успешно обновлена."
    except sqlite3.Error as e:
        print(f"Database error during category update: {e}")
        return False, "Ошибка базы данных при обновлении категории."
    finally:
        db.close()

# --- Функции для работы с пользователями (остаются без изменений) ---
def get_user_by_name(name):
    db = get_db()
    user = db.execute('SELECT id, name, password FROM users WHERE name = ?', (name,)).fetchone()
    db.close()
    return user

def get_all_users_from_db():
    db = get_db()
    users = db.execute('SELECT id, name FROM users ORDER BY name').fetchall()
    db.close()
    return users

def add_user_to_db(name, password):
    db = get_db()
    hashed_password = generate_password_hash(password)
    try:
        db.execute('INSERT INTO users (name, password) VALUES (?, ?)', (name, hashed_password))
        db.commit()
        return True, f"Пользователь '{name}' успешно добавлен."
    except sqlite3.IntegrityError:
        return False, f"Пользователь с именем '{name}' уже существует."
    finally:
        db.close()

# --- Маршруты ---
@app.route('/', methods=['GET', 'POST'])
def index():
    # ... (код index остается без изменений) ...
    if not session.get('user_id'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'date' in request.form and 'amount' in request.form: # Форма добавления расхода
            date = request.form['date']
            amount_str = request.form['amount']
            category_id_str = request.form.get('category_id', '0')

            if not date or not amount_str:
                flash("Дата и сумма обязательны для заполнения.", "error")
                return redirect(url_for('index'))
            try:
                amount = float(amount_str)
            except ValueError:
                flash("Сумма должна быть числом.", "error")
                return redirect(url_for('index'))
            
            category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else 0
            
            add_expense(date, amount, category_id)
            flash("Расход успешно добавлен!", "success")
            return redirect(url_for('index'))

    expenses_list = get_all_expenses()
    categories_list = get_all_categories_from_db()
    return render_template('index.html', expenses=expenses_list, categories_for_dropdown=categories_list)


@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (код login остается без изменений) ...
    if session.get('user_id'): 
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        user = get_user_by_name(name)

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('index'))
        else:
            flash("Неверное имя пользователя или пароль.", "error")
            return redirect(url_for('login')) 
    return render_template('login.html')

@app.route('/logout')
def logout():
    # ... (код logout остается без изменений) ...
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash("Вы успешно вышли из системы.", "info")
    return redirect(url_for('login'))


@app.route('/edit_expense/<int:expense_id>', methods=['POST'])
def edit_expense_route(expense_id):
    if not session.get('user_id'):
        return jsonify(success=False, error="Необходима авторизация"), 401 # Возвращаем JSON для AJAX
    
    date = request.form.get('date')
    amount_str = request.form.get('amount')
    category_id_str = request.form.get('category_id', '0')

    if not date or not amount_str:
        return jsonify(success=False, error="Дата и сумма обязательны"), 400
    try:
        amount = float(amount_str)
    except ValueError:
        return jsonify(success=False, error="Сумма должна быть числом"), 400

    category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else 0
    
    update_expense(expense_id, date, amount, category_id)
    return jsonify(success=True) # Сообщаем AJAX об успехе


@app.route('/categories', methods=['GET', 'POST'])
def manage_categories_page():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    error_message = None
    success_message = None

    if request.method == 'POST': # Это добавление новой категории
        name = request.form.get('name', '').strip()
        if not name:
            error_message = "Название категории не может быть пустым."
        else:
            # Проверка на существование (без учета регистра) в add_category_to_db
            added, msg = add_category_to_db(name)
            if added:
                success_message = msg
            else:
                error_message = msg
    
    categories_list = get_all_categories_from_db()
    return render_template('categories.html', categories=categories_list, error=error_message, success_message=success_message)

# НОВЫЙ МАРШРУТ для редактирования категории
@app.route('/edit_category/<int:category_id>', methods=['POST'])
def edit_category_route(category_id):
    if not session.get('user_id'):
        return jsonify(success=False, error="Необходима авторизация"), 401

    new_name = request.form.get('name', '').strip()
    if not new_name:
        return jsonify(success=False, error="Название категории не может быть пустым."), 400

    category_to_edit = get_category_by_id_from_db(category_id)
    if not category_to_edit:
        return jsonify(success=False, error="Категория не найдена."), 404
    
    # Если новое имя совпадает со старым (с учетом регистра для простоты, можно lower() для сравнения без учета),
    # то можно не обновлять, но для единообразия можно пропустить эту проверку здесь и положиться на БД/update_category_in_db
    if category_to_edit['name'] == new_name:
         return jsonify(success=True, message="Название категории не изменилось.")

    success, message = update_category_in_db(category_id, new_name)
    
    if success:
        return jsonify(success=True, message=message) # message здесь содержит "Категория успешно обновлена."
    else:
        # message здесь содержит причину ошибки (например, дубликат)
        return jsonify(success=False, error=message), 400 


@app.route('/users', methods=['GET', 'POST'])
def manage_users():
    # ... (код manage_users остается без изменений) ...
    if not session.get('user_id'):
        return redirect(url_for('login'))
    if session.get('user_name') != 'admin': 
        flash("У вас нет прав для доступа к этой странице.", "error")
        return redirect(url_for('index'))

    error_message = None
    success_message = None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')

        if not name or not password:
            error_message = "Имя пользователя и пароль не могут быть пустыми."
        elif len(password) < 6: 
             error_message = "Пароль должен содержать не менее 6 символов."
        else:
            # Проверка на существование пользователя в add_user_to_db
            added, msg = add_user_to_db(name, password)
            if added:
                success_message = msg
            else:
                error_message = msg
    
    users_list = get_all_users_from_db()
    return render_template('users.html', users=users_list, error=error_message, success_message=success_message)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)