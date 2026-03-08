import click
from flask.cli import with_appcontext
from backend.extensions import db
from backend.models.models import User

@click.command('create-super-admin')
@click.argument('email')
@with_appcontext
def create_super_admin(email):
    """Promote a given user email to Platform Owner."""
    user = User.query.filter_by(email=email).first()

    if not user:
        click.echo(click.style(f"User with email '{email}' not found. They must sign up first.", fg="red"))
        return

    user.is_platform_owner = True
    user.role = 'admin'
    db.session.commit()
    click.echo(click.style(f"Success! {email} is now a Platform Owner (Level 0 Clearance).", fg="green"))

def register_commands(app):
    app.cli.add_command(create_super_admin)
