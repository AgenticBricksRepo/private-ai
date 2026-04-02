"""Flask application factory."""

import logging
import os

from flask import Flask, g

from app.config import Config, validate_env

logger = logging.getLogger(__name__)


def create_app(testing=False):
    """Create and configure the Flask application."""
    if not testing:
        validate_env()

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
    )

    config = Config()
    if testing:
        config.TESTING = True
        config.AUTH_MODE = "dev"
    app.config.from_mapping(vars(config))
    app.secret_key = config.SECRET_KEY

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if app.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Initialize extensions
    _init_extensions(app)

    # Register blueprints
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    # Request lifecycle hooks
    @app.before_request
    def _before_request():
        from app import extensions
        if extensions.db_pool:
            g.db_conn = extensions.db_pool.getconn()

    @app.teardown_request
    def _teardown_request(exc):
        conn = g.pop("db_conn", None)
        if conn is not None:
            from app import extensions
            if exc:
                conn.rollback()
            else:
                conn.commit()
            extensions.db_pool.putconn(conn)

    # Inject tenant into template context
    @app.context_processor
    def _inject_globals():
        return {
            "tenant": getattr(g, "current_tenant", None),
            "current_user": getattr(g, "current_user", None),
        }

    return app


def _init_extensions(app):
    """Initialize DB pool, S3 client, model router, and hook runner."""
    from app import extensions
    from app.db.pool import create_pool
    from app.hooks.registry import HookRunner, HookPoint
    from app.hooks.audit_logger import AuditLogger
    from app.hooks.usage_logger import UsageLogger
    from app.hooks.session_recorder import SessionRecorder
    from app.hooks.session_audit import SessionAudit
    from app.model_router.router import ModelRouter
    from app.storage.s3 import S3Client

    extensions.db_pool = create_pool(app.config["DATABASE_URL"])
    extensions.s3_client = S3Client(
        bucket=app.config["S3_BUCKET"],
        endpoint_url=app.config["S3_ENDPOINT_URL"],
        region=app.config["AWS_REGION"],
    )
    extensions.model_router = ModelRouter(app.config)

    # Hook runner
    runner = HookRunner()
    runner.register(HookPoint.POST_TOOL, AuditLogger(extensions.db_pool))
    runner.register(HookPoint.SESSION_START, SessionAudit(extensions.db_pool))
    runner.register(HookPoint.SESSION_END, UsageLogger(extensions.db_pool))
    runner.register(HookPoint.SESSION_END, SessionRecorder(extensions.s3_client))
    runner.register(HookPoint.SESSION_END, SessionAudit(extensions.db_pool))
    extensions.hook_runner = runner

    # Tool executor
    from app.tools.executor import ToolExecutor
    extensions.tool_executor = ToolExecutor(extensions.db_pool)


def _register_blueprints(app):
    """Register all route blueprints."""
    # Auth — dev or SSO based on config
    if app.config["AUTH_MODE"] == "dev":
        from app.auth.dev_auth import dev_auth_bp
        app.register_blueprint(dev_auth_bp)
    else:
        from app.auth.sso import sso_bp
        app.register_blueprint(sso_bp)

    from app.chat.routes import chat_bp
    from app.chat.api import chat_api_bp
    from app.agents.routes import agents_bp
    from app.agents.api import agents_api_bp
    from app.tools.routes import tools_bp
    from app.tools.api import tools_api_bp
    from app.folders.routes import folders_bp
    from app.folders.api import folders_api_bp
    from app.admin.routes import admin_bp
    from app.admin.api import admin_api_bp

    for bp in [
        chat_bp, chat_api_bp,
        agents_bp, agents_api_bp,
        tools_bp, tools_api_bp,
        folders_bp, folders_api_bp,
        admin_bp, admin_api_bp,
    ]:
        app.register_blueprint(bp)


def _register_error_handlers(app):
    """Register the Flask error boundary."""

    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.exception("Unhandled exception")
        return {"error": "An unexpected error occurred"}, 500

    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Not found"}, 404

    @app.errorhandler(403)
    def forbidden(e):
        return {"error": "Forbidden"}, 403
