from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import mysql.connector
import bcrypt
import os
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)

app.secret_key = 'ughsghsighosfhgvoishguoigfo'

def get_db_connection():
    return mysql.connector.connect(
        host="***",
        user="***",
        password="***",
        database="WebCursova"
    )

def get_dishes_from_db(search_query=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = "SELECT id, name, description, price, image_url, restaurant_id FROM dishes WHERE is_available = TRUE"
    params = []
    if search_query:
        sql_query += " AND (name LIKE %s OR description LIKE %s)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
        cursor.execute(sql_query, tuple(params))
    else:
        sql_query += " ORDER BY RAND() LIMIT 8"
        cursor.execute(sql_query)
    dishes = cursor.fetchall()
    cursor.close()
    conn.close()
    return dishes


def get_restaurants_from_db(search_query=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = "SELECT id, name, description, phone, cuisine_type FROM restaurants"
    params = []
    if search_query:
        sql_query += " WHERE name LIKE %s OR description LIKE %s OR cuisine_type LIKE %s"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
        cursor.execute(sql_query, tuple(params))
    else:
        sql_query += " LIMIT 8"
        cursor.execute(sql_query)
    restaurants = cursor.fetchall()
    cursor.close()
    conn.close()

    for restaurant in restaurants:
        restaurant['average_rating'] = get_average_rating_for_restaurant(restaurant['id'])

    return restaurants


def add_dish_to_db(restaurant_id, category_id, name, description, price, image_url, is_available=True):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
        INSERT INTO dishes (restaurant_id, category_id, name, description, price, image_url, is_available)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        val = (restaurant_id, category_id, name, description, price, image_url, is_available)
        cursor.execute(sql, val)
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка додавання страви до БД: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_user_profile_from_db(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
    user_profile = cursor.fetchone()
    cursor.close()
    conn.close()
    return user_profile


def update_user_profile_in_db(user_id, name, email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET name = %s, email = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                       (name, email, user_id))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка оновлення профілю користувача: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_user_addresses_from_db(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, street, city, postal_code, notes FROM addresses WHERE user_id = %s", (user_id,))
    addresses = cursor.fetchall()
    cursor.close()
    conn.close()
    return addresses

def add_user_address_to_db(user_id, street, city, postal_code, notes):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO addresses (user_id, street, city, postal_code, notes) VALUES (%s, %s, %s, %s, %s)",
                       (user_id, street, city, postal_code, notes))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка додавання адреси: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_user_orders_from_db(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT
        o.id AS order_id,
        o.total_price,
        o.status,
        o.comment,
        o.created_at,
        r.name AS restaurant_name,
        a.street,
        a.city,
        oi.quantity,
        oi.unit_price,
        d.name AS dish_name
    FROM orders o
    LEFT JOIN restaurants r ON o.restaurant_id = r.id
    LEFT JOIN addresses a ON o.address_id = a.id
    LEFT JOIN order_items oi ON o.id = oi.order_id
    LEFT JOIN dishes d ON oi.dish_id = d.id
    WHERE o.user_id = %s
    ORDER BY o.created_at DESC, o.id, oi.id;
    """
    cursor.execute(sql_query, (user_id,))
    raw_orders = cursor.fetchall()
    cursor.close()
    conn.close()

    orders = {}
    for row in raw_orders:
        order_id = row['order_id']
        if order_id not in orders:
            orders[order_id] = {
                'order_id': order_id,
                'total_price': float(row['total_price']),
                'status': row['status'],
                'comment': row['comment'],
                'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'restaurant_name': row['restaurant_name'],
                'delivery_address': f"{row['street']}, {row['city']}" if row['street'] else 'Не вказано',
                'items': []
            }
        if row['dish_name']:
            orders[order_id]['items'].append({
                'dish_name': row['dish_name'],
                'quantity': row['quantity'],
                'unit_price': float(row['unit_price'])
            })
    return list(orders.values())

def get_restaurant_id_for_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM restaurants WHERE user_id = %s", (user_id,))
    restaurant = cursor.fetchone()
    cursor.close()
    conn.close()
    return restaurant['id'] if restaurant else None

def get_restaurant_details_by_user_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, description, phone, cuisine_type FROM restaurants WHERE user_id = %s", (user_id,))
    restaurant_details = cursor.fetchone()
    cursor.close()
    conn.close()
    return restaurant_details

def get_restaurant_details_by_id(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, description, phone, cuisine_type FROM restaurants WHERE id = %s", (restaurant_id,))
    restaurant_details = cursor.fetchone()
    cursor.close()
    conn.close()
    return restaurant_details

def update_restaurant_details_in_db(restaurant_id, name, description, phone, cuisine_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE restaurants SET name = %s, description = %s, phone = %s, cuisine_type = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (name, description, phone, cuisine_type, restaurant_id)
        )
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка оновлення деталей ресторану: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_dishes_for_restaurant(restaurant_id, search_query=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT d.id, d.name, d.description, d.price, d.image_url, d.is_available, c.name AS category_name, c.id AS category_id, d.restaurant_id
    FROM dishes d
    JOIN categories c ON d.category_id = c.id
    WHERE d.restaurant_id = %s
    """
    params = [restaurant_id]
    if search_query:
        sql_query += " AND (d.name LIKE %s OR d.description LIKE %s)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
    sql_query += " ORDER BY d.name"
    cursor.execute(sql_query, tuple(params))
    dishes = cursor.fetchall()
    cursor.close()
    conn.close()
    return dishes

def get_dish_details_by_id(dish_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, price, restaurant_id FROM dishes WHERE id = %s AND is_available = TRUE",
                   (dish_id,))
    dish = cursor.fetchone()
    cursor.close()
    conn.close()
    return dish

def update_dish_details_in_db(dish_id, restaurant_id, name, description, price, image_url, is_available, category_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT restaurant_id FROM dishes WHERE id = %s", (dish_id,))
        owner_restaurant_id = cursor.fetchone()
        if owner_restaurant_id and owner_restaurant_id['restaurant_id'] != restaurant_id:
            return False

        cursor.execute(
            "UPDATE dishes SET name = %s, description = %s, price = %s, image_url = %s, is_available = %s, category_id = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (name, description, price, image_url, is_available, category_id, dish_id)
        )
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка оновлення страви: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def delete_dish_from_db(dish_id, restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT restaurant_id FROM dishes WHERE id = %s", (dish_id,))
        owner_restaurant_id = cursor.fetchone()
        if owner_restaurant_id and owner_restaurant_id['restaurant_id'] != restaurant_id:
            return False

        cursor.execute("DELETE FROM dishes WHERE id = %s", (dish_id,))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка видалення страви: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_all_categories_from_db():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cursor.fetchall()
    cursor.close()
    conn.close()
    return categories

def get_orders_for_restaurant(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT
        o.id AS order_id,
        o.total_price,
        o.status,
        o.comment,
        o.created_at,
        u.name AS user_name,
        u.email AS user_email,
        a.street,
        a.city,
        a.postal_code,
        oi.quantity,
        oi.unit_price,
        d.name AS dish_name
    FROM orders o
    JOIN users u ON o.user_id = u.id
    LEFT JOIN addresses a ON o.address_id = a.id
    LEFT JOIN order_items oi ON o.id = oi.order_id
    LEFT JOIN dishes d ON oi.dish_id = d.id
    WHERE o.restaurant_id = %s
    ORDER BY o.created_at DESC, o.id, oi.id;
    """
    cursor.execute(sql_query, (restaurant_id,))
    raw_orders = cursor.fetchall()
    cursor.close()
    conn.close()

    orders = {}
    for row in raw_orders:
        order_id = row['order_id']
        if order_id not in orders:
            orders[order_id] = {
                'order_id': order_id,
                'total_price': float(row['total_price']),
                'status': row['status'],
                'comment': row['comment'],
                'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'user_name': row['user_name'],
                'user_email': row['user_email'],
                'delivery_address': f"{row['street']}, {row['city']}{f' ({row['postal_code']})' if row['postal_code'] else ''}" if
                row['postal_code'] else 'Не вказано',
                'items': []
            }
        if row['dish_name']:
            orders[order_id]['items'].append({
                'dish_name': row['dish_name'],
                'quantity': row['quantity'],
                'unit_price': float(row['unit_price'])
            })
    return list(orders.values())

def update_order_status_in_db(order_id, new_status, restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT restaurant_id FROM orders WHERE id = %s", (order_id,))
        owner_restaurant_id = cursor.fetchone()
        if owner_restaurant_id and owner_restaurant_id['restaurant_id'] != restaurant_id:
            print(f"Помилка: Замовлення {order_id} не належить ресторану {restaurant_id}.")
            return False

        cursor.execute("UPDATE orders SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                       (new_status, order_id))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка оновлення статусу замовлення: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_all_roles_from_db():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM roles ORDER BY name")
    roles = cursor.fetchall()
    cursor.close()
    conn.close()
    return roles

def get_all_users_with_roles_from_db():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT
        u.id AS user_id,
        u.name AS user_name,
        u.email,
        u.is_active,
        r.name AS role_name,
        r.id AS role_id,
        rest.name AS restaurant_name
    FROM users u
    JOIN roles r ON u.role_id = r.id
    LEFT JOIN restaurants rest ON u.id = rest.user_id
    ORDER BY u.id;
    """
    cursor.execute(sql_query)
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users

def admin_update_user_in_db(user_id, name, email, role_id, is_active):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET name = %s, email = %s, role_id = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (name, email, role_id, is_active, user_id)
        )
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка оновлення користувача (адмін): {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def admin_delete_user_from_db(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка видалення користувача (адмін): {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_all_orders_for_admin():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT
        o.id AS order_id,
        o.total_price,
        o.status,
        o.comment,
        o.created_at,
        u.name AS user_name,
        u.email AS user_email,
        r.name AS restaurant_name,
        a.street,
        a.city,
        a.postal_code,
        oi.quantity,
        oi.unit_price,
        d.name AS dish_name
    FROM orders o
    JOIN users u ON o.user_id = u.id
    LEFT JOIN restaurants r ON o.restaurant_id = r.id
    LEFT JOIN addresses a ON o.address_id = a.id
    LEFT JOIN order_items oi ON o.id = oi.order_id
    LEFT JOIN dishes d ON oi.dish_id = d.id
    ORDER BY o.created_at DESC, o.id, oi.id;
    """
    cursor.execute(sql_query)
    raw_orders = cursor.fetchall()
    cursor.close()
    conn.close()

    orders = {}
    for row in raw_orders:
        order_id = row['order_id']
        if order_id not in orders:
            orders[order_id] = {
                'order_id': order_id,
                'total_price': float(row['total_price']),
                'status': row['status'],
                'comment': row['comment'],
                'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'user_name': row['user_name'],
                'user_email': row['user_email'],
                'restaurant_name': row['restaurant_name'] if row['restaurant_name'] else 'N/A',
                'delivery_address': f"{row['street']}, {row['city']}{f' ({row['postal_code']})' if row['postal_code'] else ''}" if
                row['postal_code'] else 'Не вказано',
                'items': []
            }
        if row['dish_name']:
            orders[order_id]['items'].append({
                'dish_name': row['dish_name'],
                'quantity': row['quantity'],
                'unit_price': float(row['unit_price'])
            })
    return list(orders.values())

def admin_update_order_status_in_db(order_id, new_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE orders SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                       (new_status, order_id))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка оновлення статусу замовлення (адмін): {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_all_dishes_for_admin():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT
        d.id,
        d.name,
        d.description,
        d.price,
        d.image_url,
        d.is_available,
        c.name AS category_name,
        c.id AS category_id,
        r.name AS restaurant_name,
        r.id AS restaurant_id
    FROM dishes d
    JOIN categories c ON d.category_id = c.id
    JOIN restaurants r ON d.restaurant_id = r.id
    ORDER BY d.id;
    """
    cursor.execute(sql_query)
    dishes = cursor.fetchall()
    cursor.close()
    conn.close()
    return dishes

def admin_update_dish_in_db(dish_id, name, description, price, image_url, is_available, category_id, restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE dishes SET name = %s, description = %s, price = %s, image_url = %s, is_available = %s, category_id = %s, restaurant_id = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (name, description, price, image_url, is_available, category_id, restaurant_id, dish_id)
        )
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка оновлення страви (адмін): {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def admin_delete_dish_from_db(dish_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM dishes WHERE id = %s", (dish_id,))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка видалення страви (адмін): {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_all_roles_from_db():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM roles ORDER BY name")
    roles = cursor.fetchall()
    cursor.close()
    conn.close()
    return roles

def create_order_in_db(user_id, restaurant_id, address_id, payment_method, total_price, comment, order_items_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql_order = """
        INSERT INTO orders (user_id, restaurant_id, address_id, payment_method, total_price, comment)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql_order, (user_id, restaurant_id, address_id, payment_method, total_price, comment))
        order_id = cursor.lastrowid

        sql_order_item = """
        INSERT INTO order_items (order_id, dish_id, quantity, unit_price)
        VALUES (%s, %s, %s, %s)
        """
        for item in order_items_data:
            cursor.execute(sql_order_item, (order_id, item['dish_id'], item['quantity'], item['unit_price']))

        conn.commit()
        return order_id
    except mysql.connector.Error as err:
        print(f"Помилка створення замовлення: {err}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()

def get_restaurant_id_by_order_id(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT restaurant_id FROM orders WHERE id = %s", (order_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result['restaurant_id'] if result else None

def check_if_order_reviewed_by_user(order_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM reviews WHERE order_id = %s AND user_id = %s", (order_id, user_id))
    review = cursor.fetchone()
    cursor.close()
    conn.close()
    return review is not None

def get_reviewable_orders_for_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT
        o.id AS order_id,
        o.created_at,
        r.name AS restaurant_name
    FROM orders o
    JOIN restaurants r ON o.restaurant_id = r.id
    LEFT JOIN reviews rev ON o.id = rev.order_id AND rev.user_id = o.user_id
    WHERE o.user_id = %s AND o.status = 'delivered' AND rev.id IS NULL
    ORDER BY o.created_at DESC;
    """
    cursor.execute(sql_query, (user_id,))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return orders

def add_review_to_db(user_id, order_id, rating, comment):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
        INSERT INTO reviews (user_id, order_id, rating, comment)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (user_id, order_id, rating, comment))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        print(f"Помилка додавання відгуку: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_reviews_by_user_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT
        rev.id AS review_id,
        rev.rating,
        rev.comment,
        rev.created_at,
        o.id AS order_id,
        r.name AS restaurant_name
    FROM reviews rev
    JOIN orders o ON rev.order_id = o.id
    JOIN restaurants r ON o.restaurant_id = r.id
    WHERE rev.user_id = %s
    ORDER BY rev.created_at DESC;
    """
    cursor.execute(sql_query, (user_id,))
    reviews = cursor.fetchall()
    cursor.close()
    conn.close()
    return reviews

def get_reviews_by_restaurant_id(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT
        rev.id AS review_id,
        rev.rating,
        rev.comment,
        rev.created_at,
        u.name AS user_name,
        o.id AS order_id
    FROM reviews rev
    JOIN orders o ON rev.order_id = o.id
    JOIN users u ON rev.user_id = u.id
    WHERE o.restaurant_id = %s
    ORDER BY rev.created_at DESC;
    """
    cursor.execute(sql_query, (restaurant_id,))
    reviews = cursor.fetchall()
    cursor.close()
    conn.close()
    return reviews

def get_average_rating_for_restaurant(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT AVG(rev.rating) AS average_rating
    FROM reviews rev
    JOIN orders o ON rev.order_id = o.id
    WHERE o.restaurant_id = %s;
    """
    cursor.execute(sql_query, (restaurant_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return float(result['average_rating']) if result and result['average_rating'] else 0.0

def create_password_reset_token(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)

        cursor.execute("DELETE FROM password_resets WHERE user_id = %s AND used = FALSE", (user_id,))

        sql = """
        INSERT INTO password_resets (user_id, token, expires_at, used)
        VALUES (%s, %s, %s, FALSE)
        """
        cursor.execute(sql, (user_id, token, expires_at))
        conn.commit()
        return token
    except mysql.connector.Error as err:
        print(f"Помилка створення токена скидання пароля: {err}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def validate_and_use_reset_token(token, new_password):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, user_id, expires_at, used FROM password_resets WHERE token = %s", (token,))
        reset_record = cursor.fetchone()

        if not reset_record:
            return {"success": False, "error": "Недійсний або неіснуючий токен."}

        if reset_record['used']:
            return {"success": False, "error": "Цей токен вже був використаний."}

        if datetime.now() > reset_record['expires_at']:
            return {"success": False, "error": "Термін дії токена закінчився."}

        user_id = reset_record['user_id']
        reset_id = reset_record['id']

        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                       (hashed_password, user_id))

        cursor.execute("UPDATE password_resets SET used = TRUE, expires_at = CURRENT_TIMESTAMP WHERE id = %s",
                       (reset_id,))

        conn.commit()
        return {"success": True, "message": "Пароль успішно оновлено."}

    except mysql.connector.Error as err:
        print(f"Помилка валідації/використання токена скидання пароля: {err}")
        conn.rollback()
        return {"success": False, "error": "Помилка бази даних під час оновлення пароля."}
    finally:
        cursor.close()
        conn.close()

@app.route("/")
def index():
    return render_template("main.html",
                           user_logged_in=session.get('user_id') is not None,
                           user_role_id=session.get('user_role_id'))


@app.route("/login.html")
def login_page():
    if session.get('user_id'):
        return redirect(url_for('index'))
    return render_template("login.html")

@app.route("/register.html")
def register_page():
    if session.get('user_id'):
        return redirect(url_for('index'))
    return render_template("register.html")

@app.route("/register_restaurant")
def register_restaurant_page():
    return render_template("register_restaurant.html", user_logged_in=session.get('user_id') is not None)

@app.route("/forgot.html")
def forgot_page():
    return render_template("forgot.html")

@app.route("/reset_password")
def reset_password_page():
    token = request.args.get('token')
    if not token:
        return "Помилка: Токен для скидання пароля відсутній.", 400
    return render_template("reset_password.html", token=token)

@app.route("/main.html")
def main_page():
    return render_template("main.html",
                           user_logged_in=session.get('user_id') is not None,
                           user_role_id=session.get('user_role_id'))

@app.route("/restaurants")
def restaurants_page():
    return render_template("restaurants.html",
                           user_logged_in=session.get('user_id') is not None,
                           user_role_id=session.get('user_role_id'))

@app.route("/restaurant/<int:restaurant_id>/menu")
def restaurant_menu_page(restaurant_id):
    restaurant = get_restaurant_details_by_id(restaurant_id)
    if not restaurant:
        return "Ресторан не знайдено", 404
    return render_template("restaurant_menu.html",
                           user_logged_in=session.get('user_id') is not None,
                           restaurant_id=restaurant_id,
                           restaurant_name=restaurant['name'])

@app.route("/my_account")
def my_account_route():
    user_id = session.get('user_id')
    user_role_id = session.get('user_role_id')

    if not user_id:
        return redirect(url_for('login_page'))

    if user_role_id == 1:
        return render_template("client_account.html", user_logged_in=True, user_name=session.get('user_name'))
    elif user_role_id == 2:
        return render_template("restaurant_account.html", user_logged_in=True, user_name=session.get('user_name'))
    elif user_role_id == 3:
        return render_template("admin_account.html", user_logged_in=True, user_name=session.get('user_name'))
    else:
        return "Невідома роль користувача або сторінка акаунта не знайдена.", 404

@app.route("/cart")
def cart_page():
    return render_template("cart.html", user_logged_in=session.get('user_id') is not None)

@app.route("/checkout")
def checkout_page():
    if not session.get('user_id'):
        return redirect(url_for('login_page'))
    return render_template("checkout.html", user_logged_in=session.get('user_id') is not None)

@app.route("/api/register", methods=["POST"])
def register():
    email = request.form.get("email")
    password = request.form.get("password")
    confirm = request.form.get("confirmPassword")

    if not email or not password or not confirm:
        return jsonify({"error": "Всі поля обовʼязкові"}), 400

    if password != confirm:
        return jsonify({"error": "Паролі не співпадають"}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": "Email вже зареєстрований"}), 400

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        name = email.split("@")[0]
        cursor.execute("INSERT INTO users (role_id, name, email, password_hash) VALUES (%s, %s, %s, %s)",
                       (1, name, email, hashed))
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Помилка бази даних під час реєстрації користувача: {err}")
        return jsonify({"error": "Помилка сервера під час реєстрації користувача"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return jsonify({"success": True, "message": "Реєстрація користувача успішна"})

@app.route("/api/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        return jsonify({"error": "Введіть email і пароль"}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Користувача не знайдено"}), 401

        if not bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
            return jsonify({"error": "Невірний пароль"}), 401

        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_role_id'] = user['role_id']

    except mysql.connector.Error as err:
        print(f"Помилка бази даних під час входу: {err}")
        return jsonify({"error": "Помилка сервера під час входу"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return jsonify({
        "success": True,
        "message": "Успішний вхід",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "role_id": user["role_id"]
        }
    })

@app.route("/api/logout")
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_role_id', None)
    return jsonify({"success": True, "message": "Ви вийшли з акаунту"})

@app.route("/api/dishes", methods=["GET"])
def api_get_dishes():
    search_query = request.args.get('search')
    dishes = get_dishes_from_db(search_query)
    return jsonify(dishes=dishes)

@app.route("/api/restaurants", methods=["GET"])
def api_get_restaurants():
    search_query = request.args.get('search')
    restaurants = get_restaurants_from_db(search_query)
    return jsonify(restaurants=restaurants)

@app.route("/api/register_restaurant", methods=["POST"])
def api_register_restaurant():
    email = request.form.get("email")
    password = request.form.get("password")
    confirm_password = request.form.get("confirmPassword")
    restaurant_name = request.form.get("restaurantName")
    phone = request.form.get("phone")
    street = request.form.get("street")
    city = request.form.get("city")
    postal_code = request.form.get("postalCode")
    description = request.form.get("description")
    cuisine_type = request.form.get("cuisineType")

    if not all([email, password, confirm_password, restaurant_name, phone, street, city]):
        return jsonify({"error": "Будь ласка, заповніть всі обов'язкові поля."}), 400

    if password != confirm_password:
        return jsonify({"error": "Паролі не співпадають!"}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": "Email вже зареєстрований."}), 400

        cursor.execute("SELECT id FROM roles WHERE name = 'restaurant'")
        restaurant_role = cursor.fetchone()
        if not restaurant_role:
            return jsonify({"error": "Роль 'restaurant' не знайдена в базі даних. Зверніться до адміністратора."}), 500
        restaurant_role_id = restaurant_role['id']

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute(
            "INSERT INTO users (role_id, name, email, password_hash) VALUES (%s, %s, %s, %s)",
            (restaurant_role_id, restaurant_name, email, hashed_password)
        )
        conn.commit()
        user_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO addresses (user_id, street, city, postal_code) VALUES (%s, %s, %s, %s)",
            (user_id, street, city, postal_code)
        )
        conn.commit()

        cursor.execute(
            "INSERT INTO restaurants (user_id, name, description, phone, cuisine_type) VALUES (%s, %s, %s, %s, %s)",
            (user_id, restaurant_name, description, phone, cuisine_type)
        )
        conn.commit()

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Помилка бази даних під час реєстрації ресторану: {err}")
        return jsonify({"error": "Помилка сервера під час реєстрації ресторану."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return jsonify({"success": True, "message": "Ресторан успішно зареєстрований!"})

@app.route("/api/profile", methods=["GET"])
def api_get_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Користувач не увійшов."}), 401

    profile = get_user_profile_from_db(user_id)
    if profile:
        return jsonify(profile=profile)
    return jsonify({"error": "Профіль користувача не знайдено."}), 404

@app.route("/api/profile", methods=["POST"])
def api_update_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Користувач не увійшов."}), 401

    name = request.form.get('name')
    email = request.form.get('email')

    if not name or not email:
        return jsonify({"error": "Ім'я та email обов'язкові."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id))
        if cursor.fetchone():
            return jsonify({"error": "Цей email вже використовується іншим користувачем."}), 400
    except mysql.connector.Error as err:
        print(f"Помилка перевірки email: {err}")
        return jsonify({"error": "Помилка сервера під час перевірки email."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    if update_user_profile_in_db(user_id, name, email):
        session['user_name'] = name
        return jsonify({"success": True, "message": "Профіль успішно оновлено."})
    return jsonify({"error": "Не вдалося оновити профіль."}), 500

@app.route("/api/addresses", methods=["GET"])
def api_get_addresses():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Користувач не увійшов."}), 401

    addresses = get_user_addresses_from_db(user_id)
    return jsonify(addresses=addresses)

@app.route("/api/addresses", methods=["POST"])
def api_add_address():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Користувач не увійшов."}), 401

    street = request.form.get('street')
    city = request.form.get('city')
    postal_code = request.form.get('postalCode')
    notes = request.form.get('notes')

    if not street or not city:
        return jsonify({"error": "Вулиця та місто є обов'язковими."}), 400

    if add_user_address_to_db(user_id, street, city, postal_code, notes):
        return jsonify({"success": True, "message": "Адресу успішно додано."})
    return jsonify({"error": "Не вдалося додати адресу."}), 500

@app.route("/api/orders", methods=["GET"])
def api_get_orders():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Користувач не увійшов."}), 401

    orders = get_user_orders_from_db(user_id)
    return jsonify(orders=orders)

@app.route("/api/restaurant/profile", methods=["GET"])
def api_get_restaurant_profile():
    user_id = session.get('user_id')
    user_role_id = session.get('user_role_id')

    if not user_id or user_role_id != 2:
        return jsonify({"error": "Доступ заборонено. Ви не власник ресторану."}), 403

    restaurant_details = get_restaurant_details_by_user_id(user_id)
    if restaurant_details:
        return jsonify(restaurant=restaurant_details)
    return jsonify({"error": "Інформацію про ресторан не знайдено."}), 404

@app.route("/api/restaurant/profile", methods=["POST"])
def api_update_restaurant_profile():
    user_id = session.get('user_id')
    user_role_id = session.get('user_role_id')

    if not user_id or user_role_id != 2:
        return jsonify({"error": "Доступ заборонено."}), 403

    restaurant_id = get_restaurant_id_for_user(user_id)
    if not restaurant_id:
        return jsonify({"error": "Ресторан не знайдено для цього користувача."}), 404

    name = request.form.get('name')
    description = request.form.get('description')
    phone = request.form.get('phone')
    cuisine_type = request.form.get('cuisineType')

    if not all([name, phone]):
        return jsonify({"error": "Назва та телефон ресторану обов'язкові."}), 400

    if update_restaurant_details_in_db(restaurant_id, name, description, phone, cuisine_type):
        return jsonify({"success": True, "message": "Інформацію про ресторан успішно оновлено."})
    return jsonify({"error": "Не вдалося оновити інформацію про ресторан."}), 500

@app.route("/api/restaurant/dishes", methods=["GET"])
def api_get_restaurant_dishes():
    user_id = session.get('user_id')
    user_role_id = session.get('user_role_id')

    if not user_id or user_role_id != 2:
        return jsonify({"error": "Доступ заборонено."}), 403

    restaurant_id = get_restaurant_id_for_user(user_id)
    if not restaurant_id:
        return jsonify({"error": "Ресторан не знайдено для цього користувача."}), 404

    dishes = get_dishes_for_restaurant(restaurant_id)
    return jsonify(dishes=dishes)


@app.route("/api/restaurants/<int:restaurant_id>/dishes_public", methods=["GET"])
def api_get_public_restaurant_dishes(restaurant_id):
    search_query = request.args.get('search')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql_query = """
    SELECT d.id, d.name, d.description, d.price, d.image_url, d.is_available, c.name AS category_name, c.id AS category_id, d.restaurant_id
    FROM dishes d
    JOIN categories c ON d.category_id = c.id
    WHERE d.restaurant_id = %s AND d.is_available = TRUE
    """
    params = [restaurant_id]
    if search_query:
        sql_query += " AND (d.name LIKE %s OR d.description LIKE %s)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
    sql_query += " ORDER BY d.name"
    cursor.execute(sql_query, tuple(params))
    dishes = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(dishes=dishes)

@app.route("/api/restaurant/dishes", methods=["POST"])
def api_add_restaurant_dish():
    user_id = session.get('user_id')
    user_role_id = session.get('user_role_id')

    if not user_id or user_role_id != 2:
        return jsonify({"error": "Доступ заборонено."}), 403

    restaurant_id = get_restaurant_id_for_user(user_id)
    if not restaurant_id:
        return jsonify({"error": "Ресторан не знайдено для цього користувача."}), 404

    name = request.form.get('name')
    description = request.form.get('description')
    price = request.form.get('price')
    image_url = request.form.get('image_url')
    is_available = 'is_available' in request.form
    category_id = request.form.get('category_id')

    if not all([name, price, category_id]):
        return jsonify({"error": "Назва, ціна та категорія страви обов'язкові."}), 400

    try:
        price = float(price)
        category_id = int(category_id)
    except ValueError:
        return jsonify({"error": "Невірний формат ціни або категорії."}), 400

    if add_dish_to_db(restaurant_id, category_id, name, description, price, image_url, is_available):
        return jsonify({"success": True, "message": "Страву успішно додано."})
    return jsonify({"error": "Не вдалося додати страву."}), 500

@app.route("/api/restaurant/dishes/<int:dish_id>", methods=["PUT"])
def api_update_restaurant_dish(dish_id):
    user_id = session.get('user_id')
    user_role_id = session.get('user_role_id')

    if not user_id or user_role_id != 2:
        return jsonify({"error": "Доступ заборонено."}), 403

    restaurant_id = get_restaurant_id_for_user(user_id)
    if not restaurant_id:
        return jsonify({"error": "Ресторан не знайдено для цього користувача."}), 404

    data = request.form
    name = data.get('name')
    description = data.get('description')
    price = data.get('price')
    image_url = data.get('image_url')
    is_available = 'is_available' in data
    category_id = data.get('category_id')

    if not all([name, price, category_id]):
        return jsonify({"error": "Назва, ціна та категорія страви обов'язкові."}), 400

    try:
        price = float(price)
        category_id = int(category_id)
    except ValueError:
        return jsonify({"error": "Невірний формат ціни або категорії."}), 400

    if update_dish_details_in_db(dish_id, restaurant_id, name, description, price, image_url, is_available,
                                 category_id):
        return jsonify({"success": True, "message": "Страву успішно оновлено."})
    return jsonify({"error": "Не вдалося оновити страву (можливо, не належить вам)."}), 500

@app.route("/api/restaurant/dishes/<int:dish_id>", methods=["DELETE"])
def api_delete_restaurant_dish(dish_id):
    user_id = session.get('user_id')
    user_role_id = session.get('user_role_id')

    if not user_id or user_role_id != 2:
        return jsonify({"error": "Доступ заборонено."}), 403

    restaurant_id = get_restaurant_id_for_user(user_id)
    if not restaurant_id:
        return jsonify({"error": "Ресторан не знайдено для цього користувача."}), 404

    if delete_dish_from_db(dish_id, restaurant_id):
        return jsonify({"success": True, "message": "Страву успішно видалено."})
    return jsonify({"error": "Не вдалося видалити страву (можливо, не належить вам)."}), 500

@app.route("/api/restaurant/orders", methods=["GET"])
def api_get_restaurant_orders():
    user_id = session.get('user_id')
    user_role_id = session.get('user_role_id')

    if not user_id or user_role_id != 2:
        return jsonify({"error": "Доступ заборонено."}), 403

    restaurant_id = get_restaurant_id_for_user(user_id)
    if not restaurant_id:
        return jsonify({"error": "Ресторан не знайдено для цього користувача."}), 404

    orders = get_orders_for_restaurant(restaurant_id)
    return jsonify(orders=orders)

@app.route("/api/restaurant/orders/<int:order_id>/status", methods=["POST"])
def api_update_order_status(order_id):
    user_id = session.get('user_id')
    user_role_id = session.get('user_role_id')

    if not user_id or user_role_id != 2:
        return jsonify({"error": "Доступ заборонено."}), 403

    restaurant_id = get_restaurant_id_for_user(user_id)
    if not restaurant_id:
        return jsonify({"error": "Ресторан не знайдено для цього користувача."}), 404

    new_status = request.form.get('status')
    if not new_status:
        return jsonify({"error": "Новий статус не вказано."}), 400

    allowed_statuses = ['pending', 'preparing', 'ready', 'in_transit', 'delivered', 'cancelled']
    if new_status not in allowed_statuses:
        return jsonify({"error": "Недійсний статус."}), 400

    if update_order_status_in_db(order_id, new_status, restaurant_id):
        return jsonify({"success": True, "message": f"Статус замовлення {order_id} оновлено на {new_status}."})
    return jsonify({
                       "error": "Не вдалося оновити статус замовлення. Можливо, замовлення не належить вашому ресторану або сталася помилка БД."}), 500

@app.route("/api/categories", methods=["GET"])
def api_get_categories():
    categories = get_all_categories_from_db()
    return jsonify(categories=categories)

@app.route("/api/admin/users", methods=["GET"])
def api_admin_get_users():
    if session.get('user_role_id') != 3:
        return jsonify({"error": "Доступ заборонено. Потрібні права адміністратора."}), 403
    users = get_all_users_with_roles_from_db()
    return jsonify(users=users)

@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
def api_admin_update_user(user_id):
    if session.get('user_role_id') != 3:
        return jsonify({"error": "Доступ заборонено. Потрібні права адміністратора."}), 403

    name = request.form.get('name')
    email = request.form.get('email')
    role_id = request.form.get('role_id')
    is_active = 'is_active' in request.form

    if not all([name, email, role_id]):
        return jsonify({"error": "Ім'я, email та роль обов'язкові."}), 400

    try:
        role_id = int(role_id)
    except ValueError:
        return jsonify({"error": "Недійсний формат ID ролі."}), 400

    if role_id == 3:
        return jsonify({"error": "Не можна призначити роль адміністратора через цю панель."}), 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id))
        if cursor.fetchone():
            return jsonify({"error": "Цей email вже використовується іншим користувачем."}), 400
    except mysql.connector.Error as err:
        print(f"Помилка перевірки email (адмін): {err}")
        return jsonify({"error": "Помилка сервера під час перевірки email."}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    if admin_update_user_in_db(user_id, name, email, role_id, is_active):
        return jsonify({"success": True, "message": "Користувача успішно оновлено."})
    return jsonify({"error": "Не вдалося оновити користувача."}), 500

@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def api_admin_delete_user(user_id):
    if session.get('user_role_id') != 3:
        return jsonify({"error": "Доступ заборонено. Потрібні права адміністратора."}), 403

    if admin_delete_user_from_db(user_id):
        return jsonify({"success": True, "message": "Користувача успішно видалено."})
    return jsonify({"error": "Не вдалося видалити користувача."}), 500

@app.route("/api/admin/orders", methods=["GET"])
def api_admin_get_orders():
    if session.get('user_role_id') != 3:
        return jsonify({"error": "Доступ заборонено. Потрібні права адміністратора."}), 403
    orders = get_all_orders_for_admin()
    return jsonify(orders=orders)

@app.route("/api/admin/orders/<int:order_id>/status", methods=["POST"])
def api_admin_update_order_status(order_id):
    if session.get('user_role_id') != 3:
        return jsonify({"error": "Доступ заборонено. Потрібні права адміністратора."}), 403

    new_status = request.form.get('status')
    if not new_status:
        return jsonify({"error": "Новий статус не вказано."}), 400

    allowed_statuses = ['pending', 'preparing', 'ready', 'in_transit', 'delivered', 'cancelled']
    if new_status not in allowed_statuses:
        return jsonify({"error": "Недійсний статус."}), 400

    if admin_update_order_status_in_db(order_id, new_status):
        return jsonify({"success": True, "message": f"Статус замовлення {order_id} оновлено на {new_status}."})
    return jsonify({"error": "Не вдалося оновити статус замовлення."}), 500

@app.route("/api/admin/dishes", methods=["GET"])
def api_admin_get_dishes():
    if session.get('user_role_id') != 3:
        return jsonify({"error": "Доступ заборонено. Потрібні права адміністратора."}), 403
    dishes = get_all_dishes_for_admin()
    return jsonify(dishes=dishes)

@app.route("/api/admin/dishes/<int:dish_id>", methods=["PUT"])
def api_admin_update_dish(dish_id):
    if session.get('user_role_id') != 3:
        return jsonify({"error": "Доступ заборонено. Потрібні права адміністратора."}), 403

    data = request.form
    name = data.get('name')
    description = data.get('description')
    price = data.get('price')
    image_url = data.get('image_url')
    is_available = 'is_available' in data
    category_id = data.get('category_id')
    restaurant_id = data.get('restaurant_id')

    if not all([name, price, category_id, restaurant_id]):
        return jsonify({"error": "Назва, ціна, категорія та ресторан страви обов'язкові."}), 400

    try:
        price = float(price)
        category_id = int(category_id)
        restaurant_id = int(restaurant_id)
    except ValueError:
        return jsonify({"error": "Невірний формат ціни, категорії або ресторану."}), 400

    if admin_update_dish_in_db(dish_id, name, description, price, image_url, is_available, category_id, restaurant_id):
        return jsonify({"success": True, "message": "Страву успішно оновлено."})
    return jsonify({"error": "Не вдалося оновити страву."}), 500

@app.route("/api/admin/dishes/<int:dish_id>", methods=["DELETE"])
def api_admin_delete_dish(dish_id):
    if session.get('user_role_id') != 3:
        return jsonify({"error": "Доступ заборонено. Потрібні права адміністратора."}), 403

    if admin_delete_dish_from_db(dish_id):
        return jsonify({"success": True, "message": "Страву успішно видалено."})
    return jsonify({"error": "Не вдалося видалити страву."}), 500

@app.route("/api/roles", methods=["GET"])
def api_get_roles():
    if session.get('user_role_id') != 3:
        return jsonify({"error": "Доступ заборонено."}), 403
    roles = get_all_roles_from_db()
    return jsonify(roles=roles)

@app.route("/api/checkout/place_order", methods=["POST"])
def api_place_order():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Будь ласка, увійдіть, щоб оформити замовлення."}), 401

    data = request.get_json()
    address_id = data.get('address_id')
    payment_method = data.get('payment_method')
    comment = data.get('comment', '')
    cart_items = data.get('cart_items')

    if not all([address_id, payment_method, cart_items]):
        return jsonify({"error": "Неповні дані для замовлення."}), 400

    if not cart_items:
        return jsonify({"error": "Кошик порожній."}), 400

    try:
        address_id = int(address_id)
        user_addresses = get_user_addresses_from_db(user_id)
        if not any(addr['id'] == address_id for addr in user_addresses):
            return jsonify({"error": "Вибрана адреса не належить цьому користувачеві."}), 403

        total_price = 0
        processed_items = []
        restaurant_id = None

        for item in cart_items:
            dish_id = item.get('id')
            quantity = item.get('quantity')

            if not all([dish_id, quantity]) or quantity <= 0:
                return jsonify({"error": "Недійсні дані позиції в кошику."}), 400

            dish_details = get_dish_details_by_id(dish_id)
            if not dish_details:
                return jsonify({"error": f"Страву з ID {dish_id} не знайдено або вона недоступна."}), 404

            if restaurant_id is None:
                restaurant_id = dish_details['restaurant_id']
            elif restaurant_id != dish_details['restaurant_id']:
                return jsonify({"error": "Всі страви в замовленні повинні бути з одного ресторану."}), 400

            unit_price = float(dish_details['price'])
            total_price += unit_price * quantity
            processed_items.append({
                'dish_id': dish_id,
                'quantity': quantity,
                'unit_price': unit_price
            })

        if restaurant_id is None:
            return jsonify({"error": "Не вдалося визначити ресторан для замовлення."}), 400

        order_id = create_order_in_db(user_id, restaurant_id, address_id, payment_method, total_price, comment,
                                      processed_items)

        if order_id:
            return jsonify(
                {"success": True, "message": f"Замовлення №{order_id} успішно оформлено!", "order_id": order_id})
        else:
            return jsonify({"error": "Не вдалося оформити замовлення через помилку бази даних."}), 500

    except ValueError:
        return jsonify({"error": "Невірний формат даних."}), 400
    except Exception as e:
        print(f"Неочікувана помилка при оформленні замовлення: {e}")
        return jsonify({"error": "Виникла неочікувана помилка сервера."}), 500

@app.route("/api/client/reviewable_orders", methods=["GET"])
def api_get_client_reviewable_orders():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Користувач не увійшов."}), 401

    orders = get_reviewable_orders_for_user(user_id)
    for order in orders:
        order['created_at'] = order['created_at'].strftime('%Y-%m-%d %H:%M')
    return jsonify(orders=orders)

@app.route("/api/reviews", methods=["POST"])
def api_add_review():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Користувач не увійшов."}), 401

    data = request.get_json()
    order_id = data.get('order_id')
    rating = data.get('rating')
    comment = data.get('comment', '')

    if not all([order_id, rating]):
        return jsonify({"error": "ID замовлення та рейтинг є обов'язковими."}), 400

    try:
        order_id = int(order_id)
        rating = int(rating)
        if not (1 <= rating <= 5):
            return jsonify({"error": "Рейтинг має бути від 1 до 5."}), 400
    except ValueError:
        return jsonify({"error": "Невірний формат ID замовлення або рейтингу."}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, status FROM orders WHERE id = %s", (order_id,))
    order_info = cursor.fetchone()
    cursor.close()
    conn.close()

    if not order_info or order_info['user_id'] != user_id:
        return jsonify({"error": "Замовлення не знайдено або не належить вам."}), 403
    if order_info['status'] != 'delivered':
        return jsonify({"error": "Відгуки можна залишати лише для доставлених замовлень."}), 400
    if check_if_order_reviewed_by_user(order_id, user_id):
        return jsonify({"error": "Ви вже залишили відгук для цього замовлення."}), 400

    if add_review_to_db(user_id, order_id, rating, comment):
        return jsonify({"success": True, "message": "Відгук успішно додано."})
    return jsonify({"error": "Не вдалося додати відгук."}), 500

@app.route("/api/client/reviews", methods=["GET"])
def api_get_client_reviews():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Користувач не увійшов."}), 401

    reviews = get_reviews_by_user_id(user_id)
    for review in reviews:
        review['created_at'] = review['created_at'].strftime('%Y-%m-%d %H:%M')
    return jsonify(reviews=reviews)

@app.route("/api/restaurant/reviews", methods=["GET"])
def api_get_restaurant_reviews():
    user_id = session.get('user_id')
    user_role_id = session.get('user_role_id')

    if not user_id or user_role_id != 2:
        return jsonify({"error": "Доступ заборонено. Ви не власник ресторану."}), 403

    restaurant_id = get_restaurant_id_for_user(user_id)
    if not restaurant_id:
        return jsonify({"error": "Ресторан не знайдено для цього користувача."}), 404

    reviews = get_reviews_by_restaurant_id(restaurant_id)
    average_rating = get_average_rating_for_restaurant(restaurant_id)

    for review in reviews:
        review['created_at'] = review['created_at'].strftime('%Y-%m-%d %H:%M')

    return jsonify(reviews=reviews, average_rating=round(average_rating, 2))

@app.route("/api/forgot_password", methods=["POST"])
def api_forgot_password():
    email = request.form.get('email')
    if not email:
        return jsonify({"error": "Будь ласка, введіть ваш email."}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        print(f"Запит на скидання пароля для неіснуючого email: {email}")
        return jsonify(
            {"success": True, "message": "Якщо ваш email зареєстрований, ви отримаєте посилання для скидання пароля."})

    user_id = user['id']
    token = create_password_reset_token(user_id)

    if token:
        reset_link = url_for('reset_password_page', token=token, _external=True)
        print(f"--- СИМУЛЯЦІЯ НАДСИЛАННЯ EMAIL ---")
        print(f"Надіслано на: {email}")
        print(f"Посилання для скидання пароля: {reset_link}")
        print(f"---------------------------------")
        return jsonify(
            {"success": True, "message": "Якщо ваш email зареєстрований, ви отримаєте посилання для скидання пароля."})
    else:
        return jsonify({"error": "Не вдалося згенерувати токен для скидання пароля. Спробуйте ще раз."}), 500

@app.route("/api/reset_password", methods=["POST"])
def api_reset_password():
    token = request.form.get('token')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not all([token, new_password, confirm_password]):
        return jsonify({"error": "Всі поля обов'язкові."}), 400

    if new_password != confirm_password:
        return jsonify({"error": "Паролі не співпадають."}), 400

    result = validate_and_use_reset_token(token, new_password)
    if result['success']:
        return jsonify({"success": True, "message": result['message']})
    else:
        return jsonify({"error": result['error']}), 400

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')