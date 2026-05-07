import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET"])
@login_required
def index():

    stocks  = db.execute("SELECT symbol, SUM(shares) AS total_shares FROM history WHERE user_id = ? GROUP BY symbol", session["user_id"])

    total = 0

    for stock in stocks:
        quote = lookup(stock["symbol"])

        stock["price"] = quote["price"]

        shares = stock["total_shares"]

        stock["total"] = round(shares * stock["price"])

        total += stock["total"]

    rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    cash = round(rows[0]["cash"],2)

    return render_template("index.html", stocks=stocks, total=total, cash=cash)




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    if not rows:
        return apology("user not found")

    cash = rows[0]["cash"]

    if request.method == "GET":
         return render_template("buy.html", cash=cash)

    symbol = request.form.get("symbol")
    if not symbol:
        return apology("Please provide a stock")
    symbol = symbol.upper()
    stock = lookup(symbol)
    if not stock:
        return apology("Please provide a proper stock")
    share = request.form.get("share")
    try:
        share = int(share)
    except ValueError:
        return apology("Share must be a number")
    if share < 1:
        return apology("Please provide a positive share number")
    price = stock["price"]
    mult = price * share
    if mult > cash:
        return apology("Can't afford")
    result = cash - mult

    db.execute("UPDATE users SET cash = ? WHERE id = ?", result, session["user_id"])

    db.execute("INSERT INTO history (user_id, symbol, shares, price, type) VALUES (?, ?, ?, ?, ?)",
               session["user_id"], symbol, share, price, "BUY",)

    return redirect("/")


@app.route("/history")
@login_required
def history():

    history = db.execute("SELECT symbol, shares, price, time FROM history WHERE user_id = ? ORDER BY id", session["user_id"])
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")

    symbol = request.form.get("symbol")
    if not symbol:
        return apology("must provide a symbol", 403)

    result = lookup(symbol)

    if not result:
        return apology("must provide a proper symbol", 403)

    return render_template("quoted.html", result = result)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()


    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("username")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")
    if not name:
        return apology("must provide a username", 400)
    if not password:
        return apology("must provide a password", 400)
    if not confirm_password:
        return apology("must confirm the password", 400)
    if password != confirm_password:
        return apology("Passwords does not match", 400)
    checker = db.execute("SELECT username FROM users WHERE username = ?", name)
    if checker:
        return apology("username already taken", 400)
    try:
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", name, generate_password_hash(password))
    except ValueError as e:
        print(e)
        return apology("An error occurred", 400)
    rows = db.execute(
        "SELECT id FROM users WHERE username = ?", name)

    if len(rows) == 1:
        session["user_id"] = rows[0]["id"]
        return redirect("/")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    stocks = db.execute(
    "SELECT symbol, SUM(shares) AS total_shares FROM history WHERE user_id = ? GROUP BY symbol",
    session["user_id"])

    if request.method == "GET":
        return render_template("sell.html", stocks=stocks)

    symbol = request.form.get("symbol")
    shares = request.form.get("shares")

    if not symbol:
        return apology("Select your Stock", 400)

    if not shares:
        return apology("Sell a minimum of 1 of your stocks", 400)

    try:
        shares = int(shares)
    except ValueError:
        return apology("Invalid share number", 400)

    price = lookup(symbol)["price"]

    found = False

    for stock in stocks:
        if stock["symbol"] == symbol:
            found = True
            if stock["total_shares"] >= shares:
                db.execute(
                    "INSERT INTO history (user_id, symbol, shares, price, type) VALUES (?, ?, ?, ?, ?)",
                    session["user_id"], symbol, -shares, price, "SELL"
                )
                break
            else:
                return apology("Not enough shares to sell", 400)

    if not found:
        return apology("Stock not found", 400)

    return redirect("/")

