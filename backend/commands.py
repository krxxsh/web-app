import click
from flask.cli import with_appcontext
from backend.extensions import db
from backend.models.models import User

@click.command('create-super-admin')
@click.argument('email')
@with_appcontext
def create_super_admin(email):
    """Promote a given user email to Platform Owner (RESTRICTED)."""
    
    # HARDCODED SECURITY LOCK
    # Prevents anyone who clones the repo from giving themselves super admin rights.
    import os
    admin_emails_env = os.environ.get('ADMIN_EMAILS', '')
    ALLOWED_ADMINS = [email.strip() for email in admin_emails_env.split(',')] if admin_emails_env else []
    
    if email not in ALLOWED_ADMINS:
        click.echo(click.style(f"SECURITY BREACH: '{email}' is not authorized to become a Super Admin.", fg="red", bold=True))
        return

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
