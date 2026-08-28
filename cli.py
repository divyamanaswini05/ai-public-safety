"""Flask CLI commands (e.g. ``flask seed``)."""

import click
from flask import Flask


def register_cli_commands(app: Flask) -> None:
    """Attach application-specific CLI commands to the Flask app."""
    from services.seed_service import seed_database

    @app.cli.command("seed")
    def seed_command() -> None:
        """Seed default roles, settings and the initial admin account."""
        result = seed_database(app)
        click.echo(click.style(f"[seed] roles created: {result['roles']}", fg="cyan"))
        click.echo(
            click.style(f"[seed] settings created: {result['settings']}", fg="cyan")
        )
        if result["admin_created"]:
            click.echo(click.style("[seed] admin account created", fg="green"))
            click.echo(
                click.style("  email: ", fg="yellow") + "admin@sentinel.local"
            )
            click.echo(
                click.style("  password: ", fg="yellow")
                + f"{result['admin_password']}"
            )
            click.echo(
                click.style(
                    "Set ADMIN_PASSWORD in .env to choose your own password.",
                    fg="yellow",
                )
            )
        else:
            click.echo(
                click.style(
                    "[seed] admin account already exists (skipped)", fg="green"
                )
            )
