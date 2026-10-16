# PharmaCare pharmacy management prototype

A local Flask and SQLite starter app with a dashboard, inventory catalogue,
stock levels, sales entry, expiry and reorder alerts, and basic reports.

## Run on Windows

1. Install Python 3.10 or newer.
2. Open PowerShell in this folder.
3. Install dependencies and start the app:

   ```powershell
   py -m pip install -r requirements.txt
   py app.py
   ```

4. Open <http://127.0.0.1:5001/login>.
5. Sign in with the demo account: `admin` / `admin123`.

The app creates `pharmacy.db` and sample inventory the first time it starts.
Keep that database file backed up; it contains the app's records.

## Important

This is a development prototype, not a production-ready pharmacy system.
The demo account and current authentication are not suitable for real patient,
prescription, or business data. Before deployment, add secure user provisioning
and password hashing, role-based permissions, audit logging, CSRF protection,
validated stock adjustments, backups, and HTTPS behind a production WSGI server.
Do not expose Flask's development server directly to the internet. Remote use
requires a properly secured deployment and must comply with applicable pharmacy
and privacy regulations.
