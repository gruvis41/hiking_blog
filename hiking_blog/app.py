from flask import Flask
from hiking_blog import db
from flask_ckeditor import CKEditor
from flask_bootstrap import Bootstrap
from hiking_blog import login_manager
from datetime import date


def init_app():
    """
    Initialises the app, creates the database, registers the flask blueprints from
    each of the packages, and finally runs the app.
    """
    ckeditor = CKEditor()
    bootstrap = Bootstrap()
    app = Flask(__name__)
    app.config.from_object("config.Config")

    login_manager.create_login_manager(app)
    ckeditor.init_app(app)
    bootstrap.init_app(app)

    with app.app_context():
        db.instantiate_db(app)

        from hiking_blog.home import dashboard
        from hiking_blog.gear import gear
        from hiking_blog.trails import trails
        from hiking_blog import contact, auth

        app.register_blueprint(dashboard.home_bp)
        app.register_blueprint(gear.gear_bp)
        app.register_blueprint(trails.trail_bp)
        app.register_blueprint(contact.contact_bp)
        app.register_blueprint(auth.auth_bp)

        db.create_db()

        return app


if __name__ == "__main__":
    app = init_app()

    @app.context_processor
    def copyright_year():
        """
        Keeps footer copyright date current on every page of the app.
        """
        return dict(year=date.today().year)

    app.run(debug=True)
