"""Application factory for Lost It, Found It."""
import os

from flask import Flask, render_template
from flask_login import current_user

from config import Config
from .extensions import csrf, db, login_manager

DEFAULT_CATEGORIES = [
    "Electronics", "Books & Stationery", "ID & Cards", "Wallets & Bags",
    "Keys", "Clothing & Accessories", "Water Bottles & Lunch Boxes", "Other",
]


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .auth.routes import bp as auth_bp
    from .main.routes import bp as main_bp
    from .items.routes import bp as items_bp
    from .claims.routes import bp as claims_bp
    from .admin.routes import bp as admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(items_bp, url_prefix="/items")
    app.register_blueprint(claims_bp, url_prefix="/claims")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.context_processor
    def inject_globals():
        unread = current_user.unread_count() if current_user.is_authenticated else 0
        return {"unread_count": unread}

    register_error_handlers(app)
    register_cli(app)

    with app.app_context():
        db.create_all()
        seed_categories()
    return app


def seed_categories():
    from .models import Category
    if Category.query.count() == 0:
        db.session.add_all(Category(name=n) for n in DEFAULT_CATEGORIES)
        db.session.commit()


def register_error_handlers(app):
    for code in (403, 404, 413, 500):
        template = "errors/%d.html" % (code if code != 413 else 403)

        def handler(error, template=template, code=code):
            if code == 500:
                db.session.rollback()
            return render_template(template, error=error), code

        app.register_error_handler(code, handler)


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create tables and default categories: flask --app run init-db"""
        db.create_all()
        seed_categories()
        print("Database initialised.")
