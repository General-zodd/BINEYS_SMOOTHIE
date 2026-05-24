from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_file
)

import mysql.connector
import requests
import os

from werkzeug.utils import secure_filename

from reportlab.pdfgen import canvas

import matplotlib.pyplot as plt

from flask_mail import Mail, Message


# =========================================
# APP CONFIG
# =========================================

app = Flask(
    __name__,
    static_folder='static',
    template_folder='templates'
)

app.secret_key = os.getenv("SECRET_KEY")

UPLOAD_FOLDER = 'static/uploads'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# =========================================
# EMAIL CONFIG
# =========================================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True

app.config['MAIL_USERNAME'] = 'sadjartey873@gmail.com'
app.config['MAIL_PASSWORD'] = 'YOUR_APP_PASSWORD'

mail = Mail(app)


# =========================================
# ADMIN LOGIN
# =========================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"


# =========================================
# PAYSTACK
# =========================================

import os

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

# =========================================
# DATABASE
# =========================================

db = mysql.connector.connect(
    host="mysql.railway.internal",
    user="root",
    password="rCnfaOIKWJsISEqAmvcjwqbFqWludLBm",
    database="railway",
    port=3306
)

# =========================================
# HOME PAGE
# =========================================

@app.route('/')
def home():

    cursor = db.cursor()

    cursor.execute("""
        SELECT * FROM products
    """)

    products = cursor.fetchall()

    return render_template(
        "index.html",
        products=products
    )


# =========================================
# MENU PAGE
# =========================================

@app.route('/menu')
def menu():

    cursor = db.cursor()

    cursor.execute("""
        SELECT * FROM products
    """)

    products = cursor.fetchall()

    return render_template(
        "menu.html",
        products=products
    )


# =========================================
# CONTACT PAGE
# =========================================

@app.route('/contact')
def contact():
    return render_template("contact.html")


# =========================================
# REGISTER
# =========================================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        fullname = request.form['fullname']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']

        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO users
            (fullname, email, phone, password)
            VALUES (%s, %s, %s, %s)
        """, (
            fullname,
            email,
            phone,
            password
        ))

        db.commit()

        return redirect('/login')

    return render_template('register.html')


# =========================================
# LOGIN
# =========================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        cursor = db.cursor()

        cursor.execute("""
            SELECT * FROM users
            WHERE email=%s
            AND password=%s
        """, (
            email,
            password
        ))

        user = cursor.fetchone()

        if user:

            session['user_id'] = user[0]
            session['user_name'] = user[1]

            return redirect('/')

    return render_template('login.html')


# =========================================
# LOGOUT
# =========================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')


# =========================================
# ADD TO CART
# =========================================

@app.route('/add-to-cart/<int:id>')
def add_to_cart(id):

    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    cursor = db.cursor()

    cursor.execute("""
        SELECT id, quantity FROM cart
        WHERE user_id=%s AND product_id=%s
    """, (user_id, id))

    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE cart
            SET quantity = quantity + 1
            WHERE user_id=%s AND product_id=%s
        """, (user_id, id))
    else:
        cursor.execute("""
            INSERT INTO cart (user_id, product_id, quantity)
            VALUES (%s, %s, %s)
        """, (user_id, id, 1))

    db.commit()
    return redirect('/cart')


# =========================================
# CART
# =========================================

@app.route('/cart')
def cart():

    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    cursor = db.cursor()

    cursor.execute("""
        SELECT cart.id,
               products.name,
               products.price,
               cart.quantity,
               products.image

        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_id=%s
    """, (user_id,))

    rows = cursor.fetchall()

    cart_items = []

    total = 0

    for row in rows:
        item = {
            "id": row[0],
            "name": row[1],
            "price": float(row[2]),
            "qty": row[3],
            "image": row[4]
        }

        cart_items.append(item)
        total += item["price"] * item["qty"]

    return render_template(
        'cart.html',
        cart=cart_items,   # ✅ FIXED NAME
        total=total
    )

# =========================================
# CHECKOUT CART
# =========================================

@app.route('/checkout-cart', methods=['POST'])
def checkout_cart():

    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    name = request.form['name']
    phone = request.form['phone']
    payment_method = request.form['payment_method']

    cursor = db.cursor()

    cursor.execute("""
        SELECT cart.product_id,
               cart.quantity,
               products.price,
               products.stock

        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_id=%s
    """, (user_id,))

    cart_items = cursor.fetchall()

    if len(cart_items) == 0:
        return "Cart is empty"

    total_price = 0

    # STOCK CHECK
    for product_id, qty, price, stock in cart_items:

        if stock < qty:
            return f"Not enough stock for product {product_id}"

        total_price += price * qty

    # CREATE ORDER
    if payment_method == "Paystack":

        import requests

    reference = f"CART-{user_id}-{int(total_price)}"

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "email": f"{phone}@gmail.com",
        "amount": int(total_price * 100),
        "reference": reference,
        "callback_url": "http://127.0.0.1:5000/paystack/callback"
    }

    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json=data,
        headers=headers
    )

    res = response.json()

    if res["status"]:
        return redirect(res["data"]["authorization_url"])

    return "Payment failed"

    order_id = cursor.lastrowid

    # ORDER ITEMS + STOCK UPDATE
    for product_id, qty, price, stock in cart_items:

        cursor.execute("""
            INSERT INTO order_items (order_id, product_id, quantity)
            VALUES (%s, %s, %s)
        """, (order_id, product_id, qty))

        cursor.execute("""
            UPDATE products
            SET stock = stock - %s
            WHERE id=%s
        """, (qty, product_id))

    # CLEAR CART
    cursor.execute("""
        DELETE FROM cart WHERE user_id=%s
    """, (user_id,))

    db.commit()

    return render_template(
        "confirmation.html",
        order_id=order_id,
        reference=f"CART-{order_id}"
    )
# =========================================
# REMOVE FROM CART
# =========================================
@app.route('/remove-from-cart/<int:id>')
def remove_from_cart(id):

    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    cursor = db.cursor()

    cursor.execute("""
        DELETE FROM cart
        WHERE id=%s AND user_id=%s
    """, (id, user_id))

    db.commit()

    return redirect('/cart')
# =========================================
# ORDER PAGE
# =========================================

@app.route('/order')
def order_page():

    cursor = db.cursor()

    cursor.execute("""
        SELECT * FROM products
    """)

    products = cursor.fetchall()

    return render_template(
        "order.html",
        products=products
    )

# =========================================
# PLACE ORDER
# =========================================

@app.route('/order', methods=['POST'])
def place_order():

    name = request.form['name']
    phone = request.form['phone']
    product_id = request.form['product_id']
    quantity = int(request.form['quantity'])
    payment_method = request.form['payment_method']

    cursor = db.cursor()

    cursor.execute("""
        SELECT price, stock
        FROM products
        WHERE id=%s
    """, (product_id,))

    product = cursor.fetchone()

    if not product:
        return "Product not found"

    price = float(product[0])
    stock = int(product[1])

    if quantity > stock:
        return f"Only {stock} items left"

    total_price = price * quantity

    # SAVE ORDER
    cursor.execute("""
        INSERT INTO orders
        (customer_name, phone, total_price, payment_method, payment_status)
        VALUES (%s, %s, %s, %s, %s)
    """, (name, phone, total_price, payment_method, "Pending"))

    db.commit()
    order_id = cursor.lastrowid

    # SAVE ITEM
    cursor.execute("""
        INSERT INTO order_items
        (order_id, product_id, quantity)
        VALUES (%s, %s, %s)
    """, (order_id, product_id, quantity))

    # STOCK UPDATE
    cursor.execute("""
        UPDATE products
        SET stock = stock - %s
        WHERE id=%s
    """, (quantity, product_id))

    db.commit()

    # CASH
    if payment_method == "Cash":
        return render_template("confirmation.html",
                               order_id=order_id,
                               reference="CASH")

    # PAYSTACK
    if payment_method == "Paystack":

        email = f"{phone}@example.com"

        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "email": email,
            "amount": int(total_price * 100),
            "reference": f"ORDER_{order_id}",
            "callback_url": f"http://127.0.0.1:5000/payment/verify/{order_id}"
        }

        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=data,
            headers=headers
        )

        res = response.json()

        if res.get("status"):
            return redirect(res["data"]["authorization_url"])

        return f"Paystack Error: {res.get('message')}"
       # =========================================
    # PAYSTACK PAYMENT
    # =========================================

   
# =========================================
# VERIFY PAYMENT
# =========================================

@app.route('/payment/verify/<int:order_id>')
def verify_payment(order_id):

    reference = request.args.get('reference')

    headers = {
        "Authorization":
        f"Bearer {PAYSTACK_SECRET_KEY}"
    }

    response = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers=headers
    )

    result = response.json()

    if (
        result.get("data")
        and
        result["data"].get("status") == "success"
    ):

        cursor = db.cursor()

        cursor.execute("""
            UPDATE orders
            SET payment_status='Paid'
            WHERE id=%s
        """, (order_id,))

        db.commit()

        return render_template(
            "confirmation.html",
            order_id=order_id,
            reference=reference
        )

    return "Payment failed"


# =========================================
# PDF RECEIPT
# =========================================

@app.route('/receipt/<int:order_id>')
def receipt(order_id):

    cursor = db.cursor()

    cursor.execute("""
        SELECT customer_name,
               phone,
               total_price,
               payment_status,
               created_at
        FROM orders
        WHERE id=%s
    """, (order_id,))

    order = cursor.fetchone()

    if not order:
        return "Receipt not found"

    filename = f"receipt_{order_id}.pdf"

    c = canvas.Canvas(filename)

    c.setFont("Helvetica-Bold", 24)

    c.drawString(150, 800, "BINEYS SMOOTHIES")

    c.setFont("Helvetica", 14)

    c.drawString(100, 740, f"Order ID: {order_id}")
    c.drawString(100, 710, f"Customer: {order[0]}")
    c.drawString(100, 680, f"Phone: {order[1]}")
    c.drawString(100, 650, f"Amount: GH₵ {order[2]}")
    c.drawString(100, 620, f"Payment: {order[3]}")
    c.drawString(100, 590, f"Date: {order[4]}")

    c.drawString(
        100,
        520,
        "Thank you for ordering from Bineys Smoothies!"
    )

    c.save()

    return send_file(
        filename,
        as_attachment=True
    )


# =========================================
# ANALYTICS
# =========================================

# ======================
# ANALYTICS
# ======================

@app.route('/admin/analytics')
def analytics():

    if not session.get('admin'):
        return redirect('/admin/login')

    cursor = db.cursor()

    # SALES CHART
    cursor.execute("""
        SELECT DATE(created_at),
               SUM(total_price)
        FROM orders
        GROUP BY DATE(created_at)
    """)

    data = cursor.fetchall()

    dates = []
    totals = []

    for row in data:
        dates.append(str(row[0]))
        totals.append(float(row[1]))

    plt.figure(figsize=(8,5))

    plt.plot(dates, totals, marker='o')

    plt.title("Daily Sales")

    plt.xlabel("Date")
    plt.ylabel("Sales")

    plt.xticks(rotation=45)

    chart_path = "static/chart.png"

    plt.tight_layout()

    plt.savefig(chart_path)

    # TOTAL ORDERS
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]

    # TOTAL REVENUE
    cursor.execute("SELECT SUM(total_price) FROM orders")
    revenue = cursor.fetchone()[0]

    if revenue is None:
        revenue = 0

    # TOTAL PRODUCTS
    cursor.execute("SELECT COUNT(*) FROM products")
    products = cursor.fetchone()[0]

    # TOTAL CUSTOMERS
    cursor.execute("SELECT COUNT(*) FROM users")
    customers = cursor.fetchone()[0]

    return render_template(
        'analytics.html',
        chart=chart_path,
        total_orders=total_orders,
        revenue=revenue,
        products=products,
        customers=customers
    )
# =========================================
# ADMIN LOGIN
# =========================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        if (
            username == ADMIN_USERNAME
            and
            password == ADMIN_PASSWORD
        ):

            session['admin'] = True

            return redirect('/admin')

    return render_template("admin_login.html")



# =========================================
# ADMIN DASHBOARD
# =========================================

@app.route('/admin')
def admin_dashboard():

    if not session.get('admin'):
        return redirect('/admin/login')

    cursor = db.cursor()

    # GET ORDERS
    cursor.execute("""
        SELECT *
        FROM orders
        ORDER BY created_at DESC
    """)

    orders = cursor.fetchall()

    # GET PRODUCTS LIST
    cursor.execute("""
        SELECT *
        FROM products
        ORDER BY id DESC
    """)

    products_list = cursor.fetchall()

    # TOTAL REVENUE
    cursor.execute("""
        SELECT SUM(total_price)
        FROM orders
    """)

    revenue = cursor.fetchone()[0]

    if revenue is None:
        revenue = 0

    # TOTAL PRODUCTS
    cursor.execute("""
        SELECT COUNT(*)
        FROM products
    """)

    products = cursor.fetchone()[0]

    # TOTAL CUSTOMERS
    cursor.execute("""
        SELECT COUNT(*)
        FROM users
    """)

    customers = cursor.fetchone()[0]

    return render_template(
        "admin.html",
        orders=orders,
        revenue=revenue,
        products=products,
        customers=customers,
        products_list=products_list
    )


# =========================================
# ADD PRODUCT
# =========================================

@app.route('/admin/add-product', methods=['GET', 'POST'])
def add_product():

    if request.method == 'POST':

        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        stock = request.form['stock']

        image = request.files['image']

        filename = secure_filename(image.filename)

        image.save(
            os.path.join(
                app.config['UPLOAD_FOLDER'],
                filename
            )
        )

        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO products
            (
                name,
                description,
                price,
                stock,
                image
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            name,
            description,
            price,
            stock,
            filename
        ))

        db.commit()

        return redirect('/admin')

    return render_template(
        'add_product.html'
    )
# =========================================
# DELETE PRODUCT
# =========================================

@app.route('/admin/delete-product/<int:id>')
def delete_product(id):

    if not session.get('admin'):
        return redirect('/admin/login')

    cursor = db.cursor()

    # DELETE PRODUCT
    cursor.execute("""
        DELETE FROM products
        WHERE id=%s
    """, (id,))

    db.commit()

    return redirect('/admin')

# =========================================
# ADMIN LOGOUT
# =========================================

@app.route('/admin/logout')
def admin_logout():

    session.pop('admin', None)

    return redirect('/admin/login')
   # ======================
# TRACK ORDER
# ======================

@app.route('/track/<int:order_id>')
def track_order(order_id):

    cursor = db.cursor()

    cursor.execute("""
        SELECT delivery_status
        FROM orders
        WHERE id=%s
    """, (order_id,))

    order = cursor.fetchone()

    if not order:
        return "Order not found"

    return render_template(
        'tracking.html',
        status=order[0]
    )
# ======================
# UPDATE DELIVERY STATUS
# ======================

@app.route('/admin/update-delivery/<int:order_id>/<status>')
def update_delivery(order_id, status):

    if not session.get('admin'):
        return redirect('/admin/login')

    cursor = db.cursor()

    cursor.execute("""
        UPDATE orders
        SET delivery_status=%s
        WHERE id=%s
    """, (
        status,
        order_id
    ))

    db.commit()

    return redirect('/admin')
# ======================
# AI RECOMMENDATION
# ======================

@app.route('/ai', methods=['GET', 'POST'])
def ai_recommendation():

    recommendation = None

    if request.method == 'POST':

        goal = request.form['goal']

        if goal == "Energy":
            recommendation = "Mango Energy Blast"

        elif goal == "Weight Loss":
            recommendation = "Green Detox Smoothie"

        elif goal == "Detox":
            recommendation = "Berry Cleanse"

        elif goal == "Protein":
            recommendation = "Peanut Protein Shake"

    return render_template(
        'ai.html',
        recommendation=recommendation
    )
# ======================
# INVENTORY ALERTS
# ======================

@app.route('/admin/inventory')
def inventory():

    if not session.get('admin'):
        return redirect('/admin/login')

    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM products
        WHERE stock <= 5
    """)

    low_stock = cursor.fetchall()

    return render_template(
        'inventory.html',
        low_stock=low_stock
    )
# ======================
# DELIVERY MANAGEMENT
# ======================

@app.route('/admin/delivery')
def delivery():

    if not session.get('admin'):
        return redirect('/admin/login')

    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM orders
        ORDER BY created_at DESC
    """)

    orders = cursor.fetchall()

    return render_template(
        'delivery.html',
        orders=orders
    )
# ======================
# SEND EMAIL
# ======================

@app.route('/send-email/<int:order_id>')
def send_email(order_id):

    cursor = db.cursor()

    cursor.execute("""
        SELECT customer_name,
               total_price
        FROM orders
        WHERE id=%s
    """, (order_id,))

    order = cursor.fetchone()

    if not order:
        return "Order not found"

    msg = Message(
        'Bineys Smoothies Order',
        sender=app.config['MAIL_USERNAME'],
        recipients=[app.config['MAIL_USERNAME']]
    )

    msg.body = f"""
Hello {order[0]}

Your order has been received.

Order ID: {order_id}

Amount: GH₵ {order[1]}

Thank you for choosing Bineys Smoothies.
"""

    mail.send(msg)

    return "Email sent successfully"
# =========================================
# RUN APP
# =========================================

if __name__ == '__main__':

    app.run(debug=True)
