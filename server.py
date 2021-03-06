#!/usr/bin/env python3.8

# MIT License
#
# Copyright (c) 2020 TheCoder777
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import pdfhandler, confighandler, todolisthandler, dbhandler, paths, io, time, sys, bcrypt, re
import pandas as pd
from gevent.pywsgi import WSGIServer
from flask import Flask, render_template, request, redirect, send_file, session, url_for
from flask_session import Session
from user import User


app = Flask(__name__)


def validate_pw(pw,hashandsalt):
    return bcrypt.checkpw(pw.encode(), hashandsalt)


def hashpw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt())


def pws_equal(pw1, pw2):
    if pw1 == pw2:
        return True
    else:
        return False


def is_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def writepdf(data, uinput):
    packet = io.BytesIO()
    packet = pdfhandler.draw(data, uinput, packet)
    packet.seek(0)
    return pdfhandler.compile(packet)


@app.route("/")
def index():
    if not session.get("mode"):
        session["mode"] = "Dark"
    if session.get("user"):
        return redirect("user")
        # return render_template("index.html")
    else:
        return render_template("index.html")


@app.route("/edit")
def edit():
    if session.get("user"):
        data = UserDB.get_user_data(session.get("user"))
    else:
        data = confighandler.parse_config()

    start_date, end_date = pdfhandler.get_date(kw=data["kw"], type="server", nr=data["nr"], year=data["year"])
    data["sign_date"] = pdfhandler.get_a_date(type="html")
    return render_template("edit.html", data=data, start_date=start_date, end_date=end_date)


@app.route("/edit", methods=["POST"])
def get_and_return():
    if request.method == "POST":
        if request.form.get("submit"):
            uinput = dict(request.form.copy())
            del uinput["submit"]
            if session.get("user"):
                data = UserDB.get_settings_data(session.get("user"))
            else:
                data = confighandler.parse_config()

            pdf = writepdf(data, uinput)
            # confighandler.add_config_nr()  # only for local usage without users
            UserDB.increase_nr(session.get("user"))
            return send_file(pdf, as_attachment=True)

        elif request.form.get("refresh"):
            data = dict(request.form.copy())
            del data["refresh"]
            udata = UserDB.get_user_data(session.get("user"))
            start_date, end_date = pdfhandler.get_date(kw=udata["kw"], type="server", nr=data["nr"], year=data["year"])
            return render_template("edit.html", data=data, start_date=start_date, end_date=end_date)
        else:
            data = dict(request.form.copy())
            del data["refresh"]
            udata = UserDB.get_user_data(session.get("user"))
            start_date, end_date = pdfhandler.get_date(kw=udata["kw"], type="server", nr=data["nr"], year=data["year"])
            return render_template("edit.html", data=data, start_date=start_date, end_date=end_date)


@app.route("/settings")
def settings():
    if session.get("user"):
        data = UserDB.get_settings_data(session.get("user"))
    else:
        data = confighandler.parse_config()
    return render_template("settings.html", data=data, action="none")


@app.route("/settings", methods=["POST"])
def get_new_config():
    if request.method == "POST":
        data = dict(request.form.copy())
        if session.get("user"):
                if request.form.get("save"):
                    del data["save"]
                    if UserDB.update_config(session.get("user"), data):
                        new_data = UserDB.get_settings_data(session.get("user"))
                        return render_template("settings.html", data=new_data, action="success")
                    else:
                        return render_template("settings.html", data=data, action="fail")
                else:
                    return render_template("settings.html", data=data, action="fail")
        else:
            try:
                if data.get("hard_reset"):
                    confighandler.reset_config()
                    new_data = confighandler.parse_config()
                    return render_template("settings.html", data=new_data, action="success_reset")
                elif data.get("save"):
                    confighandler.update_config(data)
                    new_data = confighandler.parse_config()
                    return render_template("settings.html", data=new_data, action="success")
                else:
                    return render_template("settings.html", data=data, action="fail")
            except KeyError:
                return render_template("settings.html", data=data, action="fail")


@app.route("/login")
def login():
    return render_template("security/login.html")


@app.route("/login", methods=["POST"])
def user_login():
    if request.method == "POST":
        try:
            if request.form.get("login"):
                if not (len(request.form["name"]) > 0 and len(request.form["password"]) > 0):
                    return render_template("security/login.html", notify="nodata")
                name = request.form["name"]
                if is_email(name):
                    user = User(id=UserDB.get_id_by_email(name))
                    hashandsalt = UserDB.get_pw_by_email(name)
                else:
                    user = User(id=UserDB.get_id_by_nickname(name))
                    hashandsalt = UserDB.get_pw_by_nickname(name)
                if not hashandsalt:
                    return render_template("security/login.html", name=request.form["name"], pw=request.form["password"], notify="nouser")
                if validate_pw(str(request.form["password"]), hashandsalt):
                    session["user"] = user
                    session["user"].check_user_files()
                    global df
                    df = todolisthandler.open_todolist(session["user"].id)
                    return redirect(url_for("user"))
                else:
                    return render_template("security/login.html", name=request.form["name"], pw=request.form["password"], notify="failed")
            if request.form.get("use_as_guest"):
                return redirect(url_for("edit"))
            elif request.form.get("forgot_password"):
                return redirect(url_for("forgot_password"))
            else:
                return render_template("security/login.html", name=request.form["name"], pw=request.form["password"], notify="failed")
        except KeyError as e:
            return render_template("security/login.html", notify="failed")


@app.route("/register")
def register():
    return render_template("security/register.html")


@app.route("/register", methods=["POST"])
def get_user():
    if request.method == "POST":
        try:
            if request.form.get("register"):
                data = dict(request.form.copy())
                if not (len(request.form["name"]) > 0 and len(request.form["surname"]) > 0 and len(request.form["email"]) > 0 and len(request.form["password"])):
                    return render_template("security/register.html", data=data, notify="not_enough_data")
                name = request.form["name"]
                surname = request.form["surname"]
                email = request.form["email"]
                if not is_email(email):
                    return render_template("security/register.html", data=data, notify="invalid_email")
                if not (len(request.form["password"]) and len(request.form["password_re"])):
                    return render_template("security/register.html", data=data, notify="second_pw_needed")
                if pws_equal(request.form["password"], request.form["password_re"]):
                    pwd_and_salt = hashpw(request.form["password"])
                    UserDB.add_user(name, surname, email, pwd_and_salt)
                    session["user"] = User(id=UserDB.get_id_by_email(email))
                    session["user"].check_user_files()
                    global df
                    df = todolisthandler.open_todolist(session["user"].id)
                    return redirect(url_for("user"))
                else:
                    return render_template("security/register.html", data=data, notify="passwords_missmatch")
            elif request.form.get("use_as_guest"):
                return redirect(url_for("edit"))
            else:
                return render_template("security/register.html", data=data, notify="failed")
        except KeyError:
            return render_template("security/register.html", notify="failed")


@app.route("/user")
def user():
    if session.get("user"):
        return render_template("user.html")
    else:
        redirect(url_for("index"))


@app.route("/logout")
def logout():
    del session["user"]
    return redirect(url_for("index"))


@app.route("/forgot-password")
def forgot_password():
    return render_template("security/forgot_password.html")


@app.route("/change-password")
def change_password():
    return render_template("security/change_password.html")


@app.route("/change-mode")
def change_mode():
    print(session["mode"])
    if session["mode"] == "Dark":
        session["mode"] = "Light"
        print(session["mode"])
        return redirect(request.referrer)
    else:
        session["mode"] = "Dark"
        print(session["mode"])
        return redirect(request.referrer)


@app.route("/todolist")
def todolist():
    if session.get("user"):
        if not "df" in globals():
            df = todolisthandler.open_todolist(session["user"].id)
        return render_template("todolist.html", df=df)
    else:
        return render_template("index.html", notify="login_required")


@app.route("/todolist", methods=["POST"])
def save_todos():
    if session.get("user"):
        if not "df" in globals():
            df = todolisthandler.open_todolist(session["user"].id)
        data = dict(request.form.copy())
        if data.get("save"):
            del data["save"]

            # reset all
            for i in range(len(df.columns)):
                df[i]["done"] = False
                for j in range(len(df[i]["blocks"])):
                    df[i]["blocks"][j]["done"] = False
                    for k in range(len(df[i]["blocks"][j]["body"])):
                        df[i]["blocks"][j]["body"][k]["done"] = False

            # insert only returned
            for key in data.keys():
                if len(key) == 1:
                    key = int(key)
                    df[key]["done"] = True
                    for j in range(len(df[key]["blocks"])):
                        df[key]["blocks"][j]["done"] = True
                        for k in range(len(df[key]["blocks"][j]["body"])):
                            df[key]["blocks"][j]["body"][k]["done"] = True

                elif len(key) == 3:
                    l1, l2 = key.split(".")
                    l1, l2 = int(l1), int(l2)
                    df[l1]["blocks"][l2]["done"] = True
                    for k in range(len(df[l1]["blocks"][l2]["body"])):
                        df[l1]["blocks"][l2]["body"][k]["done"] = True

                elif len(key) == 5:
                    l1, l2, l3 = key.split(".")
                    l1, l2, l3 = int(l1), int(l2), int(l3)
                    df[l1]["blocks"][l2]["body"][l3]["done"] = True

            todolisthandler.save_todolist(session["user"].id, df)
            return render_template("todolist.html", df=df, notify="success")
        else:
            return render_template("todolist.html", df=df, notify="fail")
    else:
        print("here")
        return render_template("index.html", notify="login_required")

if __name__ == "__main__":
    HOST='localhost'
    PORT=8000
    SESSION_TYPE="filesystem"
    SESSION_FILE_DIR=paths.COOKIE_PATH
    app.config.from_object(__name__)
    Session(app)
    pdfhandler.checkup()
    UserDB = dbhandler.UserDB()
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--debug", "debug", "-d", "d"]:
            app.run(host=HOST, port=PORT, debug=True)  # for debugging
    else:
        print(f"\nRunning on http://{HOST}:{PORT}/\n")
        server = WSGIServer((HOST, PORT), app)
        server.serve_forever()
