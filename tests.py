import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json
import bcrypt

from app import app, get_db_connection, create_password_reset_token, validate_and_use_reset_token, \
    get_restaurants_from_db, add_dish_to_db, update_user_profile_in_db, get_user_orders_from_db, \
    update_order_status_in_db


class FlaskAppTests(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        with self.app as client:
            with client.session_transaction() as sess:
                sess.clear()

    @patch('app.mysql.connector.connect')
    def test_register_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 1

        response = self.app.post('/api/register', data={
            'email': 'test@example.com',
            'password': 'password123',
            'confirmPassword': 'password123'
        })
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Реєстрація користувача успішна')
        mock_cursor.execute.assert_any_call("SELECT id FROM users WHERE email = %s", ('test@example.com',))
        mock_cursor.execute.assert_any_call(
            "INSERT INTO users (role_id, name, email, password_hash) VALUES (%s, %s, %s, %s)",
            (1, 'test', 'test@example.com', unittest.mock.ANY)
        )
        mock_conn.commit.assert_called_once()

    @patch('app.get_db_connection')
    @patch('app.get_average_rating_for_restaurant')
    def test_get_restaurants_from_db(self, mock_get_average_rating, mock_get_db_connection):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {'id': 1, 'name': 'Restaurant A', 'description': 'Desc A', 'phone': '111', 'cuisine_type': 'Italian'},
            {'id': 2, 'name': 'Restaurant B', 'description': 'Desc B', 'phone': '222', 'cuisine_type': 'Asian'}
        ]
        mock_get_average_rating.side_effect = [4.5, 3.0]

        restaurants = get_restaurants_from_db()

        self.assertEqual(len(restaurants), 2)
        self.assertEqual(restaurants[0]['name'], 'Restaurant A')
        self.assertEqual(restaurants[0]['average_rating'], 4.5)
        self.assertEqual(restaurants[1]['name'], 'Restaurant B')
        self.assertEqual(restaurants[1]['average_rating'], 3.0)
        mock_cursor.execute.assert_called_once_with(
            "SELECT id, name, description, phone, cuisine_type FROM restaurants LIMIT 8")
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
        self.assertEqual(mock_get_average_rating.call_count,
                         2)

    @patch('app.get_db_connection')
    def test_add_dish_to_db_success(self, mock_get_db_connection):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = add_dish_to_db(1, 1, 'Pizza', 'Delicious pizza', 150.0, 'url_pizza.jpg', True)

        self.assertTrue(result)
        mock_cursor.execute.assert_called_once_with(
            """
        INSERT INTO dishes (restaurant_id, category_id, name, description, price, image_url, is_available)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
            (1, 1, 'Pizza', 'Delicious pizza', 150.0, 'url_pizza.jpg', True)
        )
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('app.get_db_connection')
    def test_update_user_profile_in_db_success(self, mock_get_db_connection):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = update_user_profile_in_db(1, 'New Name', 'new@example.com')

        self.assertTrue(result)
        mock_cursor.execute.assert_called_once()
        mock_cursor.execute.assert_called_once_with(
            "UPDATE users SET name = %s, email = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            ('New Name', 'new@example.com', 1)
        )
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('app.get_db_connection')
    def test_get_user_orders_from_db(self, mock_get_db_connection):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'order_id': 101, 'total_price': 250.0, 'status': 'delivered',
                'comment': 'Fast delivery', 'created_at': datetime(2023, 1, 1, 10, 0, 0),
                'restaurant_name': 'Pizzeria', 'street': 'Main St', 'city': 'Kyiv',
                'quantity': 2, 'unit_price': 100.0, 'dish_name': 'Pizza Margherita'
            },
            {
                'order_id': 101, 'total_price': 250.0, 'status': 'delivered',
                'comment': 'Fast delivery', 'created_at': datetime(2023, 1, 1, 10, 0, 0),
                'restaurant_name': 'Pizzeria', 'street': 'Main St', 'city': 'Kyiv',
                'quantity': 1, 'unit_price': 50.0, 'dish_name': 'Coca-Cola'
            },
            {
                'order_id': 102, 'total_price': 120.0, 'status': 'pending',
                'comment': '', 'created_at': datetime(2023, 1, 2, 11, 30, 0),
                'restaurant_name': 'Sushi Place', 'street': 'Side St', 'city': 'Lviv',
                'quantity': 1, 'unit_price': 120.0, 'dish_name': 'Philadelphia Roll'
            }
        ]

        orders = get_user_orders_from_db(1)

        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0]['order_id'], 101)
        self.assertEqual(orders[0]['total_price'], 250.0)
        self.assertEqual(len(orders[0]['items']), 2)
        self.assertEqual(orders[0]['items'][0]['dish_name'], 'Pizza Margherita')
        self.assertEqual(orders[1]['order_id'], 102)
        self.assertEqual(orders[1]['total_price'], 120.0)
        self.assertEqual(len(orders[1]['items']), 1)
        mock_cursor.execute.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('app.get_db_connection')
    def test_update_order_status_in_db_success(self, mock_get_db_connection):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {'restaurant_id': 1}

        result = update_order_status_in_db(101, 'preparing', 1)

        self.assertTrue(result)
        mock_cursor.execute.assert_any_call("SELECT restaurant_id FROM orders WHERE id = %s", (101,))
        mock_cursor.execute.assert_any_call(
            "UPDATE orders SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            ('preparing', 101)
        )
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('app.mysql.connector.connect')
    @patch('app.create_password_reset_token')
    @patch('app.url_for')
    def test_api_forgot_password_success(self, mock_url_for, mock_create_token, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {'id': 1, 'email': 'user@example.com'}
        mock_create_token.return_value = 'some_generated_token'
        mock_url_for.return_value = 'http://localhost/reset_password?token=some_generated_token'

        response = self.app.post('/api/forgot_password', data={'email': 'user@example.com'})
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn('Якщо ваш email зареєстрований', data['message'])
        mock_cursor.execute.assert_called_once_with("SELECT id FROM users WHERE email = %s", ('user@example.com',))
        mock_create_token.assert_called_once_with(1)
        mock_url_for.assert_called_once_with('reset_password_page', token='some_generated_token', _external=True)

    @patch('app.get_db_connection')
    def test_validate_and_use_reset_token_expired(self, mock_get_db_connection):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {
            'id': 1,
            'user_id': 10,
            'expires_at': datetime.now() - timedelta(hours=1),
            'used': False
        }

        result = validate_and_use_reset_token('expired_token', 'new_secure_password')

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Термін дії токена закінчився.')
        mock_conn.commit.assert_not_called()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()