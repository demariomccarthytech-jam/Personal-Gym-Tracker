"""A local gym tracker for user profiles and grouped workout sessions."""

import random
import sqlite3
from datetime import date, datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text


console = Console()

RETURNING_USER_GREETINGS = (
    "Welcome back, {name}. Ready to level up?",
    "Another day, another opportunity to get stronger.",
    "Good to have you back, {name}.",
    "Let's get to work, {name}.",
    "Every rep counts. Let's keep building.",
    "You're showing up. That's what matters.",
    "Time to put in the work.",
    "What's good, {name}? Ready to train?",
    "Consistency builds results. Let's get after it.",
    "Your next session starts here.",
)

# Store the database beside this Python file so it is easy to find and back up.
# SQLite is included with Python, so it needs no separate dependency.
DATABASE_PATH = Path(__file__).with_name("workouts.db")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def connect_to_database():
    """Open the SQLite database and return a connection to it."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables():
    """Create account and session tables and upgrade older workout databases."""
    with connect_to_database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                special_word TEXT NOT NULL DEFAULT '',
                date_of_birth TEXT NOT NULL,
                weight_lbs REAL NOT NULL,
                height_inches REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        user_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(users)")
        }
        if "special_word" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN special_word TEXT NOT NULL DEFAULT ''"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workout_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                session_name TEXT NOT NULL,
                workout_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, session_name, workout_date)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exercise_name TEXT NOT NULL,
                weight_lbs REAL NOT NULL,
                is_bodyweight INTEGER NOT NULL DEFAULT 0,
                sets INTEGER NOT NULL,
                reps_per_set INTEGER NOT NULL,
                total_reps INTEGER NOT NULL,
                volume_lbs REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
                day_name TEXT NOT NULL,
                UNIQUE(user_id, weekday)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_day_id INTEGER NOT NULL REFERENCES schedule_days(id) ON DELETE CASCADE,
                exercise_name TEXT NOT NULL,
                position INTEGER NOT NULL
            )
            """
        )
        workout_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(workouts)")
        }
        if "user_id" not in workout_columns:
            connection.execute(
                "ALTER TABLE workouts ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )
        if "session_id" not in workout_columns:
            connection.execute(
                "ALTER TABLE workouts ADD COLUMN session_id INTEGER "
                "REFERENCES workout_sessions(id)"
            )
        if "is_bodyweight" not in workout_columns:
            connection.execute(
                "ALTER TABLE workouts ADD COLUMN is_bodyweight "
                "INTEGER NOT NULL DEFAULT 0"
            )


def calculate_age(date_of_birth, today=None):
    """Return a person's age in whole years."""
    today = today or date.today()
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


def calculate_bmi(weight_lbs, height_inches):
    """Calculate BMI from pounds and inches."""
    return weight_lbs * 703 / (height_inches * height_inches)


def get_bmi_category(bmi):
    """Return a simple BMI category using fixed numeric ranges."""
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Healthy weight"
    if bmi < 30:
        return "Overweight"
    return "Obesity"


def get_or_create_user():
    """Sign in to an existing profile or create a new local profile."""
    while True:
        action = Prompt.ask(
            "Welcome! Choose 1) Sign in  2) Create a new profile",
            choices=["1", "2"],
        )
        if action == "1":
            name = ask_for_text("Enter your full name")
            special_word = ask_for_text("Enter your special word")
            with connect_to_database() as connection:
                user = connection.execute(
                    "SELECT id, name, date_of_birth, weight_lbs, height_inches "
                    "FROM users WHERE name = ? COLLATE NOCASE "
                    "AND special_word = ? COLLATE NOCASE",
                    (name, special_word),
                ).fetchone()
                if user is None:
                    legacy_user = connection.execute(
                        "SELECT id, name, date_of_birth, weight_lbs, height_inches "
                        "FROM users WHERE name = ? COLLATE NOCASE AND special_word = ''",
                        (name,),
                    ).fetchone()
                    if legacy_user and Prompt.ask(
                        "This existing profile needs a special word for sign-in. Save "
                        "the one you entered?",
                        choices=["y", "n"],
                        default="y",
                    ) == "y":
                        connection.execute(
                            "UPDATE users SET special_word = ? WHERE id = ?",
                            (special_word, legacy_user[0]),
                        )
                        user = legacy_user

            if user is None:
                console.print(
                    "No matching profile found. Choose Create a new profile to get started.",
                    style="yellow",
                )
                continue
            greeting = random.choice(RETURNING_USER_GREETINGS).format(name=user[1])
            console.print(greeting, style="bold green")
            break

        console.print(Panel("Let’s get you started! 🚀", border_style="cyan"))
        name = ask_for_text("Enter your Full Name")
        special_word = ask_for_text("Create your special word for sign-in")
        with connect_to_database() as connection:
            existing_user = connection.execute(
                "SELECT name FROM users WHERE name = ? COLLATE NOCASE "
                "AND special_word = ? COLLATE NOCASE",
                (name, special_word),
            ).fetchone()
        if existing_user:
            console.print(
                "That profile already exists. Choose Sign in to open it.",
                style="yellow",
            )
            continue

        while True:
            date_text = ask_for_text("Date of birth (YYYY-MM-DD)")
            try:
                birth_date = date.fromisoformat(date_text)
            except ValueError:
                console.print("Use the date format YYYY-MM-DD.", style="yellow")
                continue
            if birth_date >= date.today():
                console.print("Please Re-enter your date of birth", style="yellow")
                continue
            break
        weight_lbs = ask_for_number("Current weight (lbs)")
        height_feet = ask_for_whole_number("Height, feet")
        height_remainder = ask_for_whole_number(
            "Height, remaining inches", allow_zero=True
        )
        while height_remainder > 11:
            console.print("Enter 0 through 11 inches.", style="yellow")
            height_remainder = ask_for_whole_number(
                "Height, remaining inches", allow_zero=True
            )
        height_inches = height_feet * 12 + height_remainder
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        with connect_to_database() as connection:
            cursor = connection.execute(
                "INSERT INTO users "
                "(name, special_word, date_of_birth, weight_lbs, height_inches, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    name,
                    special_word,
                    birth_date.isoformat(),
                    weight_lbs,
                    height_inches,
                    created_at,
                ),
            )
            user = (
                cursor.lastrowid,
                name,
                birth_date.isoformat(),
                weight_lbs,
                height_inches,
            )
        console.print(f"Welcome to your new profile, {name}!", style="bold green")
        break

    with connect_to_database() as connection:
        first_user = connection.execute(
            "SELECT id FROM users ORDER BY id LIMIT 1"
        ).fetchone()
    if first_user and user[0] == first_user[0]:
        migrate_legacy_workouts(user[0])
    return user


def migrate_legacy_workouts(user_id):
    """Attach pre-account workout rows to the current user by calendar day."""
    with connect_to_database() as connection:
        legacy_rows = connection.execute(
            "SELECT id, created_at FROM workouts WHERE session_id IS NULL ORDER BY id"
        ).fetchall()
        sessions_by_day = {}
        for workout_id, created_at in legacy_rows:
            workout_date = datetime.fromisoformat(created_at).astimezone().date().isoformat()
            session_id = sessions_by_day.get(workout_date)
            if session_id is None:
                session = connection.execute(

                    """
                    SELECT id FROM workout_sessions
                    WHERE user_id = ? AND session_name = ? AND workout_date = ?
                    """,
                    (user_id, "Previous workouts", workout_date),
                ).fetchone()
                if session is None:
                    cursor = connection.execute(
                        """
                        INSERT INTO workout_sessions
                            (user_id, session_name, workout_date, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (user_id, "Previous workouts", workout_date, created_at),
                    )
                    session_id = cursor.lastrowid
                else:
                    session_id = session[0]
                sessions_by_day[workout_date] = session_id
            connection.execute(
                "UPDATE workouts SET user_id = ?, session_id = ? WHERE id = ?",
                (user_id, session_id, workout_id),
            )


def display_profile(user):
    """Show account details and the calculated BMI."""
    _, name, date_of_birth, weight_lbs, height_inches = user
    birth_date = date.fromisoformat(date_of_birth)
    age = calculate_age(birth_date)
    bmi = calculate_bmi(weight_lbs, height_inches)
    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim")
    details.add_column(style="bold")
    details.add_row("Date of birth", birth_date.isoformat())
    details.add_row("Age", f"{age} years")
    details.add_row("Weight", f"{format_weight(weight_lbs)} lbs")
    details.add_row(
        "Height", f"{int(height_inches // 12)} ft {int(height_inches % 12)} in"
    )
    details.add_row("BMI", f"{bmi:.1f}")
    details.add_row("BMI category", get_bmi_category(bmi))
    console.print(
        Panel(
            details,
            title=Text(f"Welcome, {name}", style="bold"),
            border_style="green",
        )
    )
    console.print("BMI is a screening measure, not a diagnosis.", style="dim")


def edit_profile(user):
    """Update the signed-in user's profile details and return the saved profile."""
    user_id, name, date_of_birth, weight_lbs, height_inches = user
    console.print("Leave a field blank to keep its current value.", style="dim")

    name = ask_for_text("Full name", default=name)
    birth_date = date.fromisoformat(date_of_birth)
    while True:
        date_text = Prompt.ask(
            "Date of birth (YYYY-MM-DD)", default=birth_date.isoformat()
        ).strip()
        try:
            updated_birth_date = date.fromisoformat(date_text)
        except ValueError:
            console.print("Use the date format YYYY-MM-DD.", style="yellow")
            continue
        if updated_birth_date >= date.today():
            console.print("Date of birth must be in the past.", style="yellow")
            continue
        break

    weight_lbs = ask_for_number("Current weight (lbs)", default=weight_lbs)
    height_feet = ask_for_whole_number(
        "Height, feet", default=int(height_inches // 12)
    )
    height_remainder = ask_for_whole_number(
        "Height, remaining inches",
        allow_zero=True,
        default=int(height_inches % 12),
    )
    while height_remainder > 11:
        console.print("Enter 0 through 11 inches.", style="yellow")
        height_remainder = ask_for_whole_number(
            "Height, remaining inches",
            allow_zero=True,
            default=int(height_inches % 12),
        )
    height_inches = height_feet * 12 + height_remainder

    with connect_to_database() as connection:
        connection.execute(
            "UPDATE users SET name = ?, date_of_birth = ?, weight_lbs = ?, "
            "height_inches = ? WHERE id = ?",
            (
                name,
                updated_birth_date.isoformat(),
                weight_lbs,
                height_inches,
                user_id,
            ),
        )

    updated_user = (
        user_id,
        name,
        updated_birth_date.isoformat(),
        weight_lbs,
        height_inches,
    )
    console.print("Profile updated successfully.", style="bold green")
    display_profile(updated_user)
    return updated_user


def view_profile(user):
    """Display the profile and let the user edit it or return to the menu."""
    display_profile(user)
    menu = Table.grid(padding=(0, 2))
    menu.add_column(style="bold cyan")
    menu.add_column()
    menu.add_row("1", "Edit profile")
    menu.add_row("2", "Back to main menu")
    console.print(Panel(menu, title="Profile options", border_style="blue"))
    action = Prompt.ask(
        "Choose an option",
        choices=["1", "2"],
    )
    if action == "1":
        return edit_profile(user)
    return user


def ask_for_text(prompt, default=None):
    """Ask for text until the user enters something other than blank space."""
    while True:
        answer = Prompt.ask(
            prompt.rstrip().removesuffix(":"),
            default=None if default is None else str(default),
        )
        answer = (answer or "").strip()
        if answer:
            return answer
        console.print(
            "Please enter a value. This field cannot be blank.", style="yellow"
        )


def ask_for_number(prompt, allow_zero=False, default=None):
    """Read a number and keep asking if the input is invalid.

    Set allow_zero when a field can legitimately be zero. Sets and reps use
    the whole-number helper and must be positive.
    """
    while True:
        answer = Prompt.ask(
            prompt.rstrip().removesuffix(":"),
            default=None if default is None else str(default),
        )
        answer = (answer or "").strip()
        try:
            number = float(answer)
        except ValueError:
            console.print(
                "Please enter a number, such as 25 or 12.5.", style="yellow"
            )
            continue

        # Reject negative values, and reject zero when the field needs to be
        # greater than zero. The sets/reps fields are converted to integers
        # by their own helper below.
        if number < 0 or (number == 0 and not allow_zero):
            console.print("Please enter a value greater than zero.", style="yellow")
            continue
        return number


def ask_for_whole_number(prompt, allow_zero=False, default=None):
    """Read a whole number, requiring positive values unless zero is allowed."""
    while True:
        answer = Prompt.ask(
            prompt.rstrip().removesuffix(":"),
            default=None if default is None else str(default),
        )
        answer = (answer or "").strip()
        try:
            number = int(answer)
        except ValueError:
            console.print(
                "Please enter a whole number, such as 3 or 10.", style="yellow"
            )
            continue

        if number < 0 or (number == 0 and not allow_zero):
            console.print("Please enter a number greater than zero.", style="yellow")
            continue
        return number


def collect_exercise():
    """Ask for exercise details and calculate the exercise totals."""
    console.print("\n[bold cyan]Let's get your Workout Logged!!![/bold cyan]")
    exercise_name = ask_for_text("Exercise name: ")
    weight_lbs = ask_for_number(
        "Added weight (lbs; press Enter if none)",
        allow_zero=True,
        default=0,
    )
    is_bodyweight = weight_lbs == 0
    sets = ask_for_whole_number("Number of sets: ")
    reps_per_set = ask_for_whole_number("Reps per set: ")

    # Total reps adds up every rep across all sets.
    total_reps = sets * reps_per_set

    # Workout volume is the lifted weight multiplied by all completed reps.
    # For example, 25 lbs x 3 sets x 10 reps = 750 lbs of volume.
    volume_lbs = weight_lbs * total_reps

    # Return all values together in a dictionary. A dictionary labels each
    # value, which makes the data easier to understand in the rest of the app.
    return {
        "exercise_name": exercise_name,
        "weight_lbs": weight_lbs,
        "is_bodyweight": is_bodyweight,
        "sets": sets,
        "reps_per_set": reps_per_set,
        "total_reps": total_reps,
        "volume_lbs": volume_lbs,
    }


def format_weight(value):
    """Display whole-number weights without an unnecessary decimal part."""
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def display_exercise(exercise):
    """Display one exercise in a readable, consistent format."""
    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim")
    details.add_column(style="bold")
    load_description = (
        "Bodyweight"
        if exercise["is_bodyweight"]
        else f"{format_weight(exercise['weight_lbs'])} lbs added"
    )
    details.add_row("Load", load_description)
    details.add_row(
        "Sets × reps",
        f"{exercise['sets']} × {exercise['reps_per_set']}",
    )
    details.add_row("Total reps", str(exercise["total_reps"]))
    details.add_row(
        "Added-load volume", f"{format_weight(exercise['volume_lbs'])} lbs"
    )
    console.print(
        Panel(
            details,
            title=Text(exercise["exercise_name"], style="bold"),
            border_style="cyan",
        )
    )


def get_or_create_session(user_id, session_name):
    """Return today's named workout session, creating it when needed."""
    workout_date = datetime.now().astimezone().date().isoformat()
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with connect_to_database() as connection:
        connection.execute(
            """
            INSERT INTO workout_sessions (user_id, session_name, workout_date, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, session_name, workout_date) DO NOTHING
            """,
            (user_id, session_name, workout_date, created_at),
        )
        return connection.execute(
            """
            SELECT id FROM workout_sessions
            WHERE user_id = ? AND session_name = ? AND workout_date = ?
            """,
            (user_id, session_name, workout_date),
        ).fetchone()[0]


def save_exercise(exercise, user_id, session_id, replace_existing=False):
    """Save an exercise under the current user's named workout session."""
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")

    # The question marks are placeholders. Passing values separately keeps
    # user input safe and lets SQLite handle text and numbers correctly.
    with connect_to_database() as connection:
        if replace_existing:
            connection.execute(
                "DELETE FROM workouts WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            )
        connection.execute(
            "\n"
            "            INSERT INTO workouts (\n"
            "                exercise_name, weight_lbs, is_bodyweight, sets, reps_per_set,\n"
            "                total_reps, volume_lbs, created_at, user_id, session_id\n"
            "            )\n"
            "            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n"
            "            ",
            (
                exercise["exercise_name"],
                exercise["weight_lbs"],
                int(exercise["is_bodyweight"]),
                exercise["sets"],
                exercise["reps_per_set"],
                exercise["total_reps"],
                exercise["volume_lbs"],
                created_at,
                user_id,
                session_id,
            ),
        )


def add_workout(user):
    """Add one or more exercises to a named workout session."""
    session_name = ask_for_text("Workout name (for example, Push)")
    workout_date = datetime.now().astimezone().date().isoformat()
    with connect_to_database() as connection:
        existing_session = connection.execute(
            """
            SELECT id, session_name
            FROM workout_sessions
            WHERE user_id = ? AND session_name = ? COLLATE NOCASE
              AND workout_date = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user[0], session_name, workout_date),
        ).fetchone()

    if existing_session:
        existing_session_id, existing_session_name = existing_session
        console.print(
            f"A workout named {existing_session_name!r} already exists today. "
            "Replacing it will remove its exercises.",
            style="yellow",
        )
        if Prompt.ask(
            "Replace today's workout?",
            choices=["y", "n"],
            default="n",
        ) != "y":
            console.print("Existing workout left unchanged.", style="cyan")
            return
        session_id = existing_session_id
        session_name = existing_session_name
        replace_existing = True
    else:
        session_id = get_or_create_session(user[0], session_name)
        replace_existing = False

    console.print(Text(f"\n{session_name} workout", style="bold cyan"))

    while True:
        exercise = collect_exercise()
        display_exercise(exercise)
        save_exercise(
            exercise,
            user[0],
            session_id,
            replace_existing=replace_existing,
        )
        replace_existing = False
        console.print("Exercise saved to this workout.", style="bold green")
        if Prompt.ask(
            "Add another exercise to this workout?", choices=["y", "n"], default="n"
        ) == "n":
            break
    console.print(Text(f"{session_name} workout saved.", style="bold green"))


def view_saved_workouts(user):
    """Load this user's workout sessions and display them newest-first."""
    with connect_to_database() as connection:
        rows = connection.execute(
            """
            SELECT s.workout_date, s.session_name, w.exercise_name,
                   w.weight_lbs, w.is_bodyweight, w.sets, w.reps_per_set,
                   w.total_reps, w.volume_lbs
            FROM workouts AS w
            JOIN workout_sessions AS s ON s.id = w.session_id
            WHERE w.user_id = ?
            ORDER BY s.workout_date DESC, s.id DESC, w.id DESC
            """,
            (user[0],),
        ).fetchall()

    if not rows:
        console.print(
            "\nYour workout history is looking a little empty! 💪 Let’s change that. Add your first workout to get started.",
            style="yellow",
        )
        return

    # Build overall totals as we display the saved entries.
    total_reps = 0
    total_volume = 0.0
    table = Table(title="Workout History", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Date", style="dim", no_wrap=True)
    table.add_column("Workout", style="bold")
    table.add_column("Exercise", style="bold")
    table.add_column("Load", justify="right")
    table.add_column("Sets × Reps", justify="right")
    table.add_column("Total Reps", justify="right")
    table.add_column("Added-load volume", justify="right")

    for (
        workout_date,
        session_name,
        exercise_name,
        weight,
        is_bodyweight,
        sets,
        reps,
        reps_total,
        volume,
    ) in rows:
        table.add_row(
            workout_date,
            Text(session_name),
            Text(exercise_name),
            "Bodyweight" if is_bodyweight else f"{format_weight(weight)} lbs added",
            f"{sets} × {reps}",
            str(reps_total),
            f"{format_weight(volume)} lbs",
        )
        total_reps += reps_total
        total_volume += volume

    console.print(table)

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="dim")
    summary.add_column(style="bold green")
    workout_count = len({(row[0], row[1]) for row in rows})
    summary.add_row("Saved workouts", str(workout_count))
    summary.add_row("Saved exercises", str(len(rows)))
    summary.add_row("Total reps", str(total_reps))
    summary.add_row("Total added-load volume", f"{format_weight(total_volume)} lbs")
    console.print(Panel(summary, title="Workout Summary", border_style="green"))


def load_weekly_schedule(user_id):
    """Return the user's planned day names and ordered exercises."""
    with connect_to_database() as connection:
        rows = connection.execute(
            """
            SELECT d.weekday, d.day_name, e.exercise_name
            FROM schedule_days AS d
            LEFT JOIN scheduled_exercises AS e ON e.schedule_day_id = d.id
            WHERE d.user_id = ?
            ORDER BY d.weekday, e.position, e.id
            """,
            (user_id,),
        ).fetchall()
    schedule = {weekday: {"name": "Rest Day", "exercises": []} for weekday in range(7)}
    for weekday, day_name, exercise_name in rows:
        schedule[weekday]["name"] = day_name
        if exercise_name:
            schedule[weekday]["exercises"].append(exercise_name)
    return schedule


def show_weekly_schedule(user):
    """Display a clean weekly schedule."""
    schedule = load_weekly_schedule(user[0])
    table = Table(title=Text(f"{user[1]}'s Weekly Workout Schedule"), box=box.ROUNDED,
                  header_style="bold cyan")
    table.add_column("Day", style="bold", no_wrap=True)
    table.add_column("Workout", style="cyan")
    table.add_column("Exercises")
    for weekday, day in enumerate(WEEKDAYS):
        entry = schedule[weekday]
        exercises = ", ".join(entry["exercises"]) or "—"
        table.add_row(day, Text(entry["name"]), Text(exercises))
    console.print(table)


def manage_schedule_day(user, weekday):
    """View and edit the selected weekday's workout plan."""
    with connect_to_database() as connection:
        connection.execute(
            """INSERT INTO schedule_days (user_id, weekday, day_name)
               VALUES (?, ?, 'Rest Day') ON CONFLICT(user_id, weekday) DO NOTHING""",
            (user[0], weekday),
        )
        day_id, day_name = connection.execute(
            "SELECT id, day_name FROM schedule_days WHERE user_id = ? AND weekday = ?",
            (user[0], weekday),
        ).fetchone()

    while True:
        with connect_to_database() as connection:
            exercises = connection.execute(
                "SELECT id, exercise_name FROM scheduled_exercises "
                "WHERE schedule_day_id = ? ORDER BY position, id", (day_id,)
            ).fetchall()
        console.print(Text(f"\n{WEEKDAYS[weekday]} — {day_name}", style="bold cyan"))
        if exercises:
            for index, (_, exercise_name) in enumerate(exercises, 1):
                console.print(Text(f"{index}. {exercise_name}"))
        else:
            console.print("No exercises planned.", style="dim")
        action = Prompt.ask(
            "1) Rename workout  2) Add exercise  3) Remove exercise  "
            "4) Create workout for this day  5) Choose a saved workout  "
            "6) Clear this day  7) Back",
            choices=["1", "2", "3", "4", "5", "6", "7"],
        )
        if action == "7":
            return
        if action == "1":
            day_name = ask_for_text("Workout name (for example, Push Day)")
            with connect_to_database() as connection:
                connection.execute(
                    "UPDATE schedule_days SET day_name = ? WHERE id = ? AND user_id = ?",
                    (day_name, day_id, user[0]),
                )
        elif action == "2":
            if day_name == "Rest Day" and not exercises:
                day_name = ask_for_text("Workout name (for example, Push Day)")
                with connect_to_database() as connection:
                    connection.execute(
                        "UPDATE schedule_days SET day_name = ? WHERE id = ? AND user_id = ?",
                        (day_name, day_id, user[0]),
                    )
            exercise_name = ask_for_text("Exercise name")
            with connect_to_database() as connection:
                position = connection.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 FROM scheduled_exercises "
                    "WHERE schedule_day_id = ?", (day_id,)
                ).fetchone()[0]
                connection.execute(
                    "INSERT INTO scheduled_exercises (schedule_day_id, exercise_name, position) "
                    "VALUES (?, ?, ?)", (day_id, exercise_name, position)
                )
        elif action == "3":
            if not exercises:
                console.print("There are no exercises to remove.", style="yellow")
                continue
            choices = [str(index) for index in range(1, len(exercises) + 1)] + ["0"]
            selected = Prompt.ask("Choose exercise to remove (0 to cancel)", choices=choices)
            if selected != "0":
                exercise_id = exercises[int(selected) - 1][0]
                with connect_to_database() as connection:
                    connection.execute(
                        "DELETE FROM scheduled_exercises WHERE id = ? AND schedule_day_id = ?",
                        (exercise_id, day_id),
                    )
        elif action == "4":
            if (exercises or day_name != "Rest Day") and Prompt.ask(
                "Replace the workout already planned for this day?",
                choices=["y", "n"],
                default="n",
            ) != "y":
                continue
            day_name = ask_for_text("Workout name (for example, Leg Day)")
            planned_exercises = []
            while True:
                planned_exercises.append(ask_for_text("Exercise name"))
                if Prompt.ask(
                    "Add another exercise?", choices=["y", "n"], default="n"
                ) == "n":
                    break
            with connect_to_database() as connection:
                connection.execute(
                    "UPDATE schedule_days SET day_name = ? WHERE id = ? AND user_id = ?",
                    (day_name, day_id, user[0]),
                )
                connection.execute(
                    "DELETE FROM scheduled_exercises WHERE schedule_day_id = ?", (day_id,)
                )
                connection.executemany(
                    "INSERT INTO scheduled_exercises (schedule_day_id, exercise_name, position) "
                    "VALUES (?, ?, ?)",
                    [(day_id, name, position) for position, name in enumerate(planned_exercises, 1)],
                )
            console.print(f"{day_name} added to {WEEKDAYS[weekday]}.", style="bold green")
        elif action == "5":
            with connect_to_database() as connection:
                saved_workouts = connection.execute(
                    """SELECT s.id, s.workout_date, s.session_name, COUNT(w.id)
                       FROM workout_sessions AS s
                       JOIN workouts AS w ON w.session_id = s.id AND w.user_id = s.user_id
                       WHERE s.user_id = ?
                       GROUP BY s.id
                       ORDER BY s.workout_date DESC, s.id DESC""",
                    (user[0],),
                ).fetchall()
            if not saved_workouts:
                console.print("Save a workout with exercises first, then you can add it here.", style="yellow")
                continue
            console.print("\nYour saved workouts:")
            for index, (_, workout_date, session_name, exercise_count) in enumerate(
                saved_workouts, 1
            ):
                console.print(Text(
                    f"{index}. {workout_date} — {session_name} ({exercise_count} exercises)"
                ))
            choices = [str(index) for index in range(1, len(saved_workouts) + 1)] + ["0"]
            selected = Prompt.ask("Choose a workout to add to this day (0 to cancel)", choices=choices)
            if selected == "0":
                continue
            session_id, _, saved_name, _ = saved_workouts[int(selected) - 1]
            saved_name = saved_name.strip() or "Workout"
            with connect_to_database() as connection:
                saved_exercises = connection.execute(
                    """SELECT w.exercise_name FROM workouts AS w
                       JOIN workout_sessions AS s ON s.id = w.session_id
                       WHERE s.user_id = ? AND w.user_id = ? AND s.id = ?
                       ORDER BY w.id""",
                    (user[0], user[0], session_id),
                ).fetchall()
            if (exercises or day_name != "Rest Day") and Prompt.ask(
                "Replace the workout already planned for this day?",
                choices=["y", "n"],
                default="n",
            ) != "y":
                continue
            with connect_to_database() as connection:
                connection.execute(
                    "UPDATE schedule_days SET day_name = ? WHERE id = ? AND user_id = ?",
                    (saved_name, day_id, user[0]),
                )
                connection.execute(
                    "DELETE FROM scheduled_exercises WHERE schedule_day_id = ?", (day_id,)
                )
                connection.executemany(
                    "INSERT INTO scheduled_exercises (schedule_day_id, exercise_name, position) "
                    "VALUES (?, ?, ?)",
                    [(day_id, exercise[0], position) for position, exercise in enumerate(saved_exercises, 1)],
                )
            day_name = saved_name
            console.print(f"{saved_name} added to {WEEKDAYS[weekday]}.", style="bold green")
        elif action == "6":
            if day_name == "Rest Day" and not exercises:
                console.print("This day is already clear.", style="dim")
                continue
            if Prompt.ask(
                f"Clear {WEEKDAYS[weekday]}'s workout and mark it as a rest day?",
                choices=["y", "n"],
                default="n",
            ) == "y":
                with connect_to_database() as connection:
                    connection.execute(
                        "DELETE FROM scheduled_exercises WHERE schedule_day_id = ?", (day_id,)
                    )
                    connection.execute(
                        "UPDATE schedule_days SET day_name = 'Rest Day' "
                        "WHERE id = ? AND user_id = ?",
                        (day_id, user[0]),
                    )
                day_name = "Rest Day"
                console.print(f"{WEEKDAYS[weekday]} is now a rest day.", style="green")


def manage_weekly_schedule(user):
    """Show and edit this user's weekly workout schedule."""
    while True:
        show_weekly_schedule(user)
        action = Prompt.ask(
            "Schedule: 1) Select a day to view/edit  2) Show weekly view  3) Back",
            choices=["1", "2", "3"],
        )
        if action == "3":
            return
        if action == "2":
            show_weekly_schedule(user)
            continue
        day_choice = Prompt.ask(
            "Select a day: " + "  ".join(f"{i + 1}) {day}" for i, day in enumerate(WEEKDAYS))
            + "  0) Back",
            choices=[str(i) for i in range(8)],
        )
        if day_choice != "0":
            manage_schedule_day(user, int(day_choice) - 1)


def manage_workout_history(user):
    """View or delete workout sessions, or clear this user's history."""
    while True:
        action = Prompt.ask(
            "Manage workouts: 1) View history  2) Delete a workout  "
            "3) Clear all history  4) Back",
            choices=["1", "2", "3", "4"],
        )
        if action == "4":
            return
        if action == "1":
            view_saved_workouts(user)
            continue
        if action == "3":
            if Prompt.ask(
                "Delete all of your workout history? This cannot be undone",
                choices=["y", "n"],
                default="n",
            ) == "y":
                with connect_to_database() as connection:
                    connection.execute(
                        "DELETE FROM workouts WHERE user_id = ?", (user[0],)
                    )
                    connection.execute(
                        "DELETE FROM workout_sessions WHERE user_id = ?", (user[0],)
                    )
                console.print("Workout history cleared.", style="bold green")
            continue

        with connect_to_database() as connection:
            sessions = connection.execute(
                """
                SELECT s.id, s.workout_date, s.session_name, COUNT(w.id)
                FROM workout_sessions AS s
                LEFT JOIN workouts AS w ON w.session_id = s.id
                WHERE s.user_id = ?
                GROUP BY s.id
                ORDER BY s.workout_date DESC, s.id DESC
                """,
                (user[0],),
            ).fetchall()

        if not sessions:
            console.print("There are no workouts to delete.", style="yellow")
            continue

        console.print("\nWorkout sessions:")
        for index, (
            _,
            workout_date,
            session_name,
            exercise_count,
        ) in enumerate(sessions, 1):
            console.print(
                f"{index}. {workout_date} — {session_name} ({exercise_count} exercises)"
            )
        choices = [str(index) for index in range(1, len(sessions) + 1)] + ["0"]
        selected = Prompt.ask("Choose a workout to delete (0 to cancel)", choices=choices)
        if selected == "0":
            continue

        session_id, workout_date, session_name, _ = sessions[int(selected) - 1]
        if Prompt.ask(
            f"Delete {session_name} from {workout_date} and all its exercises?",
            choices=["y", "n"],
            default="n",
        ) != "y":
            continue
        with connect_to_database() as connection:
            connection.execute(
                "DELETE FROM workouts WHERE session_id = ? AND user_id = ?",
                (session_id, user[0]),
            )
            connection.execute(
                "DELETE FROM workout_sessions WHERE id = ? AND user_id = ?",
                (session_id, user[0]),
            )
        console.print("Workout deleted.", style="bold green")


def show_menu():
    """Print the program's main menu."""
    menu = Table.grid(padding=(0, 2))
    menu.add_column(style="bold cyan")
    menu.add_column()
    menu.add_row("1", "Add a workout")
    menu.add_row("2", "Manage workouts")
    menu.add_row("3", "Manage weekly schedule")
    menu.add_row("4", "View profile")
    menu.add_row("5", "Exit")
    menu.add_row("6", "Sign out / switch user")
    console.print(Panel(menu, title="Personal Gym Tracker", border_style="blue"))


def main():
    """Run the app until the user exits, allowing profile switching."""
    create_tables()
    while True:
        user = get_or_create_user()
        display_profile(user)

        while True:
            show_menu()
            choice = Prompt.ask(
                "Choose an option", choices=["1", "2", "3", "4", "5", "6"]
            )

            if choice == "1":
                add_workout(user)
            elif choice == "2":
                manage_workout_history(user)
            elif choice == "3":
                manage_weekly_schedule(user)
            elif choice == "4":
                user = view_profile(user)
            elif choice == "5":
                console.print(
                    "Every rep counts. Keep pushing! 💪 See you next session.",
                    style="bold green",
                )
                return
            elif choice == "6":
                console.print("Returning to sign in...", style="cyan")
                break


# This check means main() runs when this file is launched directly, but not
# when another Python file imports these functions in a future phase.
if __name__ == "__main__":
    main()
